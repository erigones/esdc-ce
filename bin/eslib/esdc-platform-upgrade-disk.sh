#!/bin/bash

set -e

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
ESLIB="${ESLIB:-"${ERIGONES_HOME}/bin/eslib"}"

# shellcheck disable=SC1090
. "${ESLIB}/functions.sh"

PLATFORM_VER="${1}"
if [[ -z "${PLATFORM_VER}" ]]; then
	echo "Usage:   $0 <new_dc_version|new_platform_version> [--keep-smf-db] [-v] [-f] [-y]"
	echo "Example: $0 v3.0.1"
	echo "Example: $0 20180105T193033Z"
	echo "Example: $0 platform-20190107T203140Z.tgz"
	echo "Parameters:"
	echo "  --keep-smf-db     don't clear SMF database (useful if you don't want to loose"
	echo "                    your manual changes to any SMF service properties)"
	echo "  -v                verbose"
	echo "  -f                force upgrade even when the requested version is already running"
	echo "  -y                assume \"yes\" as default answer for all questions (e.g. activate new BE)"

	exit 1
fi


# default arguments
PLATFORM_VERSION_MAP_URL="https://download.danube.cloud/esdc/factory/platform/esdc-version-map.json"
# curl: 15s conn T/O; allow redirects; 1000s max duration, fail on 404
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 1000 -f"
CURL_QUIET="-s"
VERBOSE=0
KEEP_SMF_DB=0
FORCE=0

# process additional arguments
shift
while [[ ${#} -gt 0 ]]; do
	case "${1}" in
		"--keep-smf-db")
			KEEP_SMF_DB=1
			;;
		"-v")
			CURL_QUIET=""
			VERBOSE=1
			;;
		"-f")
			FORCE=1
			;;
		"-y")
			YES=1
			;;
		*)
			echo "ERROR: Unknown argument '${1}'"
			exit 10
			;;
	esac
	shift
done


#####################################################
# Functions
#####################################################

function restore_efi_partitions()
{
	declare -A disks
	local bad_part_found=0
	local good_part_found=0

	# for partition recovery
	local verified_partition=
	local partitions_for_recovery=
	local bad_counter=0
	local error_during_recovery=0

	printmsg "Checking for EFI partitions"

	for disk in $(_get_zpool_efi_disks); do
		fulldisk="/dev/dsk/${disk}s0"
		if _check_fstyp ${fulldisk} "pcfs"; then
			# EFI disk ok
			disks["${disk}"]=0
			good_part_found=1
		else
			disks["${disk}"]=1
			bad_part_found=1
		fi
	done

	if [[ "${#disks[@]}" -eq 0 ]]; then
		# zpool created without EFI partitions or no zpool disks found
		printmsg "EFI boot partitons not detected. Skipping EFI update."

	elif [[ "${bad_part_found}" -eq 0 ]] && [[ "${good_part_found}" -eq 1 ]]; then
		printmsg "EFI partitions look correct on all disks."

	elif [[ "${bad_part_found}" -eq 1 ]] && [[ "${good_part_found}" -eq 0 ]]; then
		echo "WARNING: All EFI partitions within zones pool seem to be corrupted. If that's really true, you \
will not be able to boot using UEFI at next reboot. The most probable case is that you have replaced all disks \
without running esdc-platform-upgrade. If you run into boot problems, switch to BIOS boot and/or reinstal the EFI \
partitions. Detected disks in zones pool: ${!disks[@]}"

	elif [[ "${bad_part_found}" -eq 1 ]] && [[ "${good_part_found}" -eq 1 ]]; then
		if [[ "${YES}" -ne 1 ]]; then
			printmsg "Some EFI partitions seem to be corrupted. Most probably some disks were added or replaced."
			read -p "*** Recover the corrupted EFI partitons? [Y/n] " -n 1 -r confirm
			echo
			if [[ -n "${confirm}" ]] && [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
				printmsg "Skipping the EFI recovery"
				return 0
			fi
		else
			printmsg "Some EFI partitions seem to be corrupted. Starting recovery."
		fi


		# create list of bad partitions
		for disk in ${!disks[@]}; do
			fulldisk="/dev/dsk/${disk}s0"
			if [[ "${disks["${disk}"]}" -ne 0 ]]; then
				partitions_for_recovery[$bad_counter]="${fulldisk}"	
				((++bad_counter)) || true
			elif [[ -z "${verified_partition}" ]]; then
				if _verify_efi_part "${fulldisk}"; then
					# we have found the first partition that can be used as a source to recover the corrupted ones
					verified_partition="${fulldisk}"
				fi
			fi
		done

		if [[ -z "${verified_partition}" ]]; then
			echo "WARNING: Cannot find any usable EFI partitions as a source for recovery. Please reinstall EFI \
partitons manually or use BIOS boot if you encounter UEFI boot problems."
			return 0
		fi

		[[ "${VERBOSE}" -eq 1 ]] && echo "Partitions to restore: ${partitions_for_recovery[@]}"
		[[ "${VERBOSE}" -eq 1 ]] && echo "Verified partition to use as a source: ${verified_partition}"

		# partitions rewrite start
		for part in ${partitions_for_recovery[@]}; do
			[[ "${VERBOSE}" -eq 1 ]] && echo "Recovering partition ${part}"
			if ! ${DD} "if=${verified_partition}" "of=${part}" bs=1M &> /dev/null; then
				((++error_during_recovery)) || true
			fi
		done

		if [[ "${error_during_recovery}" -eq 0 ]]; then
			printmsg "EFI recovery successfull (${#partitions_for_recovery[@]} partitions)."
		elif [[ "${error_during_recovery}" < "${#partitions_for_recovery[@]}" ]]; then
			echo "WARNING: Restore of some corrupted EFI partitions has failed. The UEFI boot process should not \
be affected as there is still enough usable EFI partitions. If you encounter boot problems, use BIOS boot."
			printmsg "EFI recovery ended"
		elif [[ "${error_during_recovery}" == "${#partitions_for_recovery[@]}" ]]; then
			echo "WARNING: Restore of all corrupted partitions has failed. Please reinstall EFI partitons manually \
or use BIOS boot if you encounter UEFI boot problems."
			printmsg "EFI recovery ended"
		fi
	fi

}


#####################################################
# Functions END
#####################################################


# check if it's a local file
if [[ -f "${PLATFORM_VER}" ]] && [[ "${PLATFORM_VER}" =~ platform-[0-9]+T[0-9]+Z\.tgz$ ]]; then
	PLATFORM_FILE="${PLATFORM_VER}"
	PLATFORM_VER="$(echo "${PLATFORM_VER}" | sed -re 's/^.*platform-([0-9]+T[0-9]+Z)\.tgz$/\1/')"
fi

# check platform version format
if [[ ! "${PLATFORM_VER}" =~ ^[0-9]+T[0-9]+Z$ ]] && [[ ! "${PLATFORM_VER}" =~ ^v[0-9]+\.[0-9]+ ]]; then
	die 2 "Unknown format of platform version: ${PLATFORM_VER}"
fi

# query platform version from esdc version if needed
if [[ "${PLATFORM_VER}" =~ ^v[0-9]+\.[0-9]+ ]]; then
	printmsg "ESDC version given, translating to platform version"
	# escape dots in version string and remove "v" from beginning
	search_version="$(echo "${PLATFORM_VER#v}" | ${SED} 's/\./\\./g')"
	pi_version=""

	printmsg "Downloading platform version list"
	# shellcheck disable=SC2086
	PLATFORM_MAP="$(${CURL} ${CURL_QUIET} ${CURL_DEFAULT_OPTS} "${PLATFORM_VERSION_MAP_URL}" || \
		die 5 "Cannot download platform map. Please check your internet connection.")"

	if [[ -z "${PLATFORM_MAP}" ]] || ! echo "${PLATFORM_MAP}" | ${JSON} --validate; then
		die 3 "Could not download a valid platform map from ${PLATFORM_VERSION_MAP_URL}"
	fi

	# query version number
	# if not found, remove the minor number and try again
	while [[ -n "${search_version}" ]]; do
		pi_version="$(echo "${PLATFORM_MAP}" | ${JSON} "${search_version}")"

		if [[ -z "${pi_version}" ]]; then
			# remove minor number
			search_version="${search_version%\\.*}"
		else
			break
		fi
	done

	if [[ -z "${pi_version}"  ]]; then
		die 3 "Could not find platform number for ESDC version ${PLATFORM_VER}"
	else
		PLATFORM_VER="${pi_version}"
		printmsg "The platform version is ${PLATFORM_VER}"
	fi
fi


# check what platform we currently run
OLD_PLATFORM_VER="$(uname -v | ${SED} 's/^[a-z]*_//')"
if [[ "${FORCE}" -ne 1 ]] && [[ "${PLATFORM_VER}" == "${OLD_PLATFORM_VER}" ]]; then
	printmsg "The requested platform version is already running. Not upgrading."
	restore_efi_partitions
	exit 0
fi


UPG_DIR="${UPGRADE_DIR:-"/opt/upgrade"}"
PLATFORM_DIR="${UPG_DIR}/platform"
[[ -z "${PLATFORM_FILE}" ]] && PLATFORM_FILE="${UPG_DIR}/platform-${PLATFORM_VER}.tgz"
BOOT_ARCHIVE="${PLATFORM_DIR}/platform-${PLATFORM_VER}/i86pc/amd64/boot_archive"
MOUNT_DIR="${UPG_DIR}/mnt"
DCOS_MNTDIR="${MOUNT_DIR}/dcos"
PLATFORM_MOUNT_DIR="${MOUNT_DIR}/platform"
USR_ARCHIVE="${PLATFORM_MOUNT_DIR}/usr.lgz"
USR_ARCHIVE_MOUNT_DIR="${MOUNT_DIR}/usr"
PLATFORM_DOWNLOAD_URL="https://download.danube.cloud/esdc/factory/platform/platform-${PLATFORM_VER}.tgz"
FINISHED_SUCCESSFULLY=0
ACTIVATE_BE=1

post_cleanup() {
	printmsg "Cleaning up"
	_beadm_umount_be "${NEW_BE}"
	umount_path "${USR_ARCHIVE_MOUNT_DIR}"
	lofi_remove "${USR_LOOPDEV}"
	umount_path "${PLATFORM_MOUNT_DIR}"
	lofi_remove "${PLATFORM_LOOPDEV}"
	rm -rf "${UPG_DIR}"
}
cleanup() {
	if [[ ${FINISHED_SUCCESSFULLY} -eq 1 ]]; then
		post_cleanup
		if [[ "${ACTIVATE_BE}" -eq 1 ]]; then
			printmsg "Please reboot as soon as possible"
		else
			printmsg "Please activate the new boot environment and reboot"
		fi
	else
		echo
		printmsg "UPGRADE FAILED!"
		echo
		post_cleanup
		if _beadm_check_be_exists "${NEW_BE}"; then
			printmsg "Removing new BE"
			_beadm_destroy_be "${NEW_BE}"
		fi
	fi
}

### START ###

# pre-flight-check
if [[ -a "${UPG_DIR}" ]]; then
	die 1 "Upgrade dir (${UPG_DIR}) exists. Please remove it first."
fi

trap cleanup EXIT

printmsg "Creating temporary dirs in ${UPG_DIR}"
mkdir -p "${UPG_DIR}" "${PLATFORM_DIR}" "${PLATFORM_MOUNT_DIR}" "${USR_ARCHIVE_MOUNT_DIR}"

# correct the dcos-1
# (issue https://github.com/erigones/esdc-factory/issues/94)
if _beadm_check_be_exists "dcos-1"; then
	if [[ "$(${ZFS} get -Ho value canmount zones/ROOT/dcos-1)" != "noauto" ]]; then
		${ZFS} set canmount=noauto zones/ROOT/dcos-1
	fi
	if [[ "$(${ZFS} get -Ho value org.opensolaris.libbe:uuid zones/ROOT/dcos-1)" == "-" ]]; then
		# assign a unique BE identifier to dcos-1
		${ZFS} set "org.opensolaris.libbe:uuid=$(uuidgen)" zones/ROOT/dcos-1
	fi
fi

# start download
printmsg "Downloading the new platform"

if [[ ! -f "${PLATFORM_FILE}" ]]; then
	PLATFORM_TMPFILE="${PLATFORM_FILE}.part"
	rm -f "${PLATFORM_TMPFILE}"
	# shellcheck disable=SC2086
	if ${CURL} ${CURL_QUIET} ${CURL_DEFAULT_OPTS} -o "${PLATFORM_TMPFILE}" "${PLATFORM_DOWNLOAD_URL}"; then
		# file successfully downloaded
		mv -f "${PLATFORM_TMPFILE}" "${PLATFORM_FILE}"
	else
		rm -f "${PLATFORM_TMPFILE}"
		die 5 "Failed to download new platform archive. Please check your internet connection."
	fi
fi

printmsg "Extracting the new platform"
${TAR} zxf "${PLATFORM_FILE}" -C "${PLATFORM_DIR}"

printmsg "Accessing the new platform files"
PLATFORM_LOOPDEV="$(lofi_add "${BOOT_ARCHIVE}")"
${MOUNT} -F ufs "${PLATFORM_LOOPDEV}" "${PLATFORM_MOUNT_DIR}"
USR_LOOPDEV="$(lofi_add "${USR_ARCHIVE}")"
${MOUNT} -r -F ufs "${USR_LOOPDEV}" "${USR_ARCHIVE_MOUNT_DIR}"

NEW_BE="$(_beadm_get_next_be_name)"
printmsg "Creating a new boot environment: ${NEW_BE}"

if [[ -z "${NEW_BE}" ]]; then
	die 5 "Cannot determine name of new boot environment"
fi

${BEADM} create "${NEW_BE}"
${BEADM} mount "${NEW_BE}" "${DCOS_MNTDIR}"

printmsg "Updating the new boot environment in the background"
${RSYNC} -ac --delete --exclude=boot/loader.conf "${PLATFORM_MOUNT_DIR}/"{bin,boot,kernel,lib,platform,sbin,smartdc} "${DCOS_MNTDIR}"
${RSYNC} -ac --delete "${USR_ARCHIVE_MOUNT_DIR}/"  "${DCOS_MNTDIR}/usr/"
${RSYNC} -a --delete "${PLATFORM_DIR}/platform-${PLATFORM_VER}/i86pc/amd64" "${DCOS_MNTDIR}/platform/i86pc"
if [[ "$(cat "${DCOS_MNTDIR}/boot/loader.conf")" == 'boot-args="-B smartos=true,computenode=true"' ]]; then 
	# replace old loader.conf from esdc_20190422T104439Z and lower
	cat << EOF > "${DCOS_MNTDIR}/boot/loader.conf"
console="text,ttya,ttyb,ttyc,ttyd"
os_console="text"
ttya-mode="115200,8,n,1,-"
ttyb-mode="115200,8,n,1,-"
ttyc-mode="115200,8,n,1,-"
ttyd-mode="115200,8,n,1,-"
loader_logo="danubecloud"
loader_brand="danubecloud"
root_shadow='\$5\$2HOHRnK3\$NvLlm.1KQBbB0WjoP7xcIwGnllhzp2HnT.mDO7DpxYA'
smartos="true"
computenode="true"
EOF
fi
printmsg "Update boot_archive checksum"
checksum "${DCOS_MNTDIR}/platform/i86pc/amd64/boot_archive" > "${DCOS_MNTDIR}/platform/i86pc/amd64/boot_archive.hash"
chown -R root:root "${DCOS_MNTDIR}/platform/i86pc/amd64"

if [[ ${KEEP_SMF_DB} -ne 1 ]]; then
	printmsg "Update SMF database from the new platform"
	cp -af "${PLATFORM_MOUNT_DIR}/etc/svc/repository.db" "${DCOS_MNTDIR}/etc/svc/repository.db"
fi

if [[ -f "${DCOS_MNTDIR}/etc/issue" ]]; then
	set +e
	printmsg "Update version in /etc/issue"
	${SED} -i '' -e "s/${OLD_PLATFORM_VER}/${PLATFORM_VER}/g" "${DCOS_MNTDIR}/etc/issue"
	set -e
fi

if [[ "${YES}" -ne 1 ]]; then
	read -p "*** Activate the new boot environment at next reboot? [Y/n] " -n 1 -r confirm
	echo
	if [[ -n "${confirm}" ]] && [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
		ACTIVATE_BE=0
	fi
fi


if [[ "${ACTIVATE_BE}" -eq 1 ]]; then
	printmsg "Activating the new boot environment at next reboot"
	_beadm_activate_be "${NEW_BE}"
fi

FINISHED_SUCCESSFULLY=1

restore_efi_partitions

printmsg "Upgrade completed successfully"
