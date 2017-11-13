#!/bin/bash

set -e

. "$(dirname $0)/functions.sh"

PLATFORM_VER="${1}"
if [[ -z "${PLATFORM_VER}" ]]; then
	echo "Usage:   $0 <new_platform_version> [--keep-smf-db] [-v] [-f]"
	echo "Example: $0 20170624T192838Z"
	echo "Args:"
	echo "  --keep-smf-db       don't clear SMF database (useful if you don't want to loose"
	echo "                      your manual changes to any SMF service properties)"
	echo "  -v                  verbose download"
	echo "  -f                  force upgrade even when the requested version is already running"

	exit 1
fi

if ! [[ "${PLATFORM_VER}" =~ ^[0-9]+T[0-9]+Z$ ]]; then
	die 2 "Unknown format of platform version: ${PLATFORM_VER}"
fi

# process additional arguments
# curl: 15s conn T/O; allow redirects; 1000s max duration; cert noverify
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 1000 -k"
CURL_OPTS="-s"
KEEP_SMF_DB=0
FORCE="0"
shift
while [[ ${#} -gt 0 ]]; do
	case "${1}" in
		"--keep-smf-db")
			KEEP_SMF_DB=1
			;;
		"-v")
			CURL_OPTS=""
			;;
		"-f")
			FORCE="1"
			;;
		*)
			echo "WARNING: Ignoring unknown argument '${1}'"
			;;
	esac
	shift
done

if [[ "${FORCE}" -ne 1 ]] && [[ "${PLATFORM_VER}" == "$(uname -v | sed 's/^[a-z]*_//')" ]]; then
	die 0 "The requested platform version is already running. Aborting upgrade."
fi


UPG_DIR="${UPGRADE_DIR:-"/opt/upgrade"}"
PLATFORM_DIR="${UPG_DIR}/platform"
PLATFORM_FILE="${UPG_DIR}/platform-${PLATFORM_VER}.tgz"
BOOT_ARCHIVE="${PLATFORM_DIR}/platform-${PLATFORM_VER}/i86pc/amd64/boot_archive"
MOUNT_DIR="${UPG_DIR}/mnt"
DCOS_MNTDIR="${MOUNT_DIR}/dcos"
PLATFORM_MOUNT_DIR="${MOUNT_DIR}/platform"
USR_ARCHIVE="${PLATFORM_MOUNT_DIR}/usr.lgz"
USR_ARCHIVE_MOUNT_DIR="${MOUNT_DIR}/usr"
PLATFORM_DOWNLOAD_URL="https://download.erigones.org/esdc/factory/platform/platform-${PLATFORM_VER}.tgz"
FINISHED_SUCCESSFULLY=0

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
${CURL} ${CURL_OPTS} ${CURL_DEFAULT_OPTS} -o "${PLATFORM_FILE}" "${PLATFORM_DOWNLOAD_URL}"
printmsg "Extracting the new platform"
${TAR} zxf "${PLATFORM_FILE}" -C "${PLATFORM_DIR}"

printmsg "Accessing the new platform files"
PLATFORM_LOOPDEV="$(lofi_add "${BOOT_ARCHIVE}")"
${MOUNT} -F ufs "${PLATFORM_LOOPDEV}" "${PLATFORM_MOUNT_DIR}"
USR_LOOPDEV="$(lofi_add "${USR_ARCHIVE}")"
${MOUNT} -r -F ufs "${USR_LOOPDEV}" "${USR_ARCHIVE_MOUNT_DIR}"

printmsg "Creating a new boot environment"
NEW_BE="$(_beadm_get_next_be_name)"
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

printmsg "Activating the new boot environment at next reboot"
_beadm_activate_be "${NEW_BE}"

FINISHED_SUCCESSFULLY=1
printmsg "Upgrade completed successfuly"
printmsg "Please reboot as soon as possible"
