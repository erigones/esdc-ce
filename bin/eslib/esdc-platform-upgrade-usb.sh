#!/bin/bash

set -e

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
ESLIB="${ESLIB:-"${ERIGONES_HOME}/bin/eslib"}"

. "${ESLIB}/functions.sh"

ESDC_VER="${1}"
if [[ -z "${ESDC_VER}" ]]; then
	echo "Usage:   $0 <new_dc_version> [-v] [-f]"
	echo "Example: $0 v2.6.7"
	echo "Args:"
	echo "  -v                verbose download"
	echo "  -f                force upgrade even when the requested version is already installed"

	exit 1
fi

if ! [[ "${ESDC_VER}" =~ ^v[0-9]\.[0-9]\.[0-9]$ ]]; then
	die 2 "Unknown format of Danube Cloud version: ${ESDC_VER}"
fi

# process additional arguments
# curl: 15s conn T/O; allow redirects; 1000s max duration
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 3600"
CURL_OPTS="-s"
FORCE="0"
shift
while [[ ${#} -gt 0 ]]; do
	case "${1}" in
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

cleanup() {
	if [[ ${FINISHED_SUCCESSFULLY} -ne 1 ]]; then
		echo
		printmsg "UPGRADE FAILED!"
		echo
	fi
	rm -rf "${UPG_DIR}"
}


# *** GLOBALS ***

NEW_USB_VER="${ESDC_VER/v}"
UPG_DIR="${UPGRADE_DIR:-"/opt/upgrade"}"
FINISHED_SUCCESSFULLY=0

# *** START ***

printmsg "Verifying current installation"

if [[ -a "${UPG_DIR}" ]]; then
	die 1 "Upgrade dir (${UPG_DIR}) exists. Please remove it first."
fi

mount_usb_key

USBMNT="$(_usbkey_get_mountpoint)"
USB_DEV="$(_usbkey_get_device)"
USB_VERSION_FILE="${USBMNT}/version"

if [[ -z "${USB_DEV}" ]]; then
	die 2 "ESDC USB key not found. Aborting."
fi
if ! [[ -f "${USB_VERSION_FILE}" ]]; then
	die 3 "Invalid or unknown USB key format. Aborting upgrade."
fi

CURR_USB_VER="$(cat "${USB_VERSION_FILE}" | sed -e 's/^esdc-.e-.n-//')"
WANTED_USB_IMG_VARIANT="$(cat "${USB_VERSION_FILE}" | sed -re 's/^(esdc-.e-.n-).*/\1/')"
if [[ ${FORCE} -ne 1 ]] && [[ "${CURR_USB_VER}" == "${NEW_USB_VER}" ]]; then
	die 0 "Requested ESDC version is already on the USB key. Nothing to do."
fi

umount_usb_key

printmsg "Downloading new platform"
ESDC_IMG="${WANTED_USB_IMG_VARIANT}${NEW_USB_VER}.img"
ESDC_IMG_FULL="${UPG_DIR}/${ESDC_IMG}"
ESDC_DOWNLOAD_URL="https://download.erigones.org/esdc/usb/stable/${ESDC_IMG}.gz"

trap cleanup EXIT

mkdir -p "${UPG_DIR}"
${CURL} ${CURL_OPTS} ${CURL_DEFAULT_OPTS} -o "${ESDC_IMG_FULL}.gz" "${ESDC_DOWNLOAD_URL}"
printmsg "Unpacking new platform"
${GZIP} -d "${ESDC_IMG_FULL}.gz"

# start upgrade
printmsg "Writing new platform image to the USB"
# change trailing p1 for p0 (c1t1d0p1 -> c1t1d0p0)
${DD} if="${ESDC_IMG_FULL}" of="${USB_DEV/p1*}p0" bs=16M

printmsg "Mounting newly written USB key into ${USBMNT}"
# mount exactly the same dev that was written to
${MOUNT} -F pcfs -o foldcase,noatime "${USB_DEV}" "${USBMNT}"

printmsg "Verifying newly written USB key"
CURR_USB_VER="$(cat "${USB_VERSION_FILE}" | sed -e 's/^esdc-.e-.n-//')"
printmsg "ESDC version on USB: ${CURR_USB_VER}"

FINISHED_SUCCESSFULLY=1

printmsg "Upgrade completed successfuly"
printmsg "Please reboot to load new platform"

