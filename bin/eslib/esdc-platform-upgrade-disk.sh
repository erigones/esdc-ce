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
	echo "  -v                verbose download"
	echo "  -f                force upgrade even when the requested version is already running"
	echo "  -y                assume \"yes\" as default answer for all questions"

	exit 1
fi


# default arguments
PLATFORM_VERSION_MAP_URL="https://download.erigones.org/esdc/factory/platform/esdc-version-map.json"
# curl: 15s conn T/O; allow redirects; 1000s max duration, fail on 404
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 1000 -f"
CURL_QUIET="-s"
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
			;;
		"-f")
			FORCE=1
			;;
		"-y")
			YES=1
			;;
		*)
			echo "WARNING: Ignoring unknown argument '${1}'"
			;;
	esac
	shift
done

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
	die 0 "The requested platform version is already running. Aborting upgrade."
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
PLATFORM_DOWNLOAD_URL="https://download.erigones.org/esdc/factory/platform/platform-${PLATFORM_VER}.tgz"
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
	# shellcheck disable=SC2086
	if ! ${CURL} ${CURL_QUIET} ${CURL_DEFAULT_OPTS} -o "${PLATFORM_FILE}" "${PLATFORM_DOWNLOAD_URL}"; then
		die 5 "Cannot download new platform archive. Please check your internet connection."
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
printmsg "Update boot_archive checksum"
checksum "${DCOS_MNTDIR}/platform/i86pc/amd64/boot_archive" > "${DCOS_MNTDIR}/platform/i86pc/amd64/boot_archive.hash"
chown -R root:root "${DCOS_MNTDIR}/platform/i86pc/amd64"

if [[ ${KEEP_SMF_DB} -ne 1 ]]; then
	printmsg "Clear SMF database so it can be recreated at reboot"
	rm -f "${DCOS_MNTDIR}/etc/svc/repository.db"
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

printmsg "Upgrade completed successfully"
