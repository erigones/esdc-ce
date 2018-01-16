#!/bin/bash

set -e

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
ESLIB="${ESLIB:-"${ERIGONES_HOME}/bin/eslib"}"

# shellcheck disable=SC1090
. "${ESLIB}/functions.sh"

ESDC_VER="${1}"
if [[ -z "${ESDC_VER}" ]]; then
	echo "Usage:   $0 <new_dc_version> [-v] [-f] [-y]"
	echo "Example: $0 v3.0.1"
	echo "Parameters:"
	echo "  -v                verbose download"
	echo "  -f                force upgrade even when the requested version is already installed"
	echo "  -y                assume \"yes\" as default answer for all questions"

	exit 1
fi

if ! [[ "${ESDC_VER}" =~ ^v[0-9]+\.[0-9]+ ]]; then
	die 2 "Unknown format of Danube Cloud version: ${ESDC_VER}"
fi

# process additional arguments
# curl: 15s conn T/O; allow redirects; 1000s max duration, fail on 404
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 3600 -f"
CURL_QUIET="-s"
FORCE=0
YES=0
shift
while [[ ${#} -gt 0 ]]; do
	case "${1}" in
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

cleanup() {
	if [[ ${FINISHED_SUCCESSFULLY} -ne 1 ]]; then
		echo
		printmsg "UPGRADE FAILED!"
		echo
	fi
	rm -rf "${UPG_DIR}"
}


# *** GLOBALS ***

NEW_USB_VER="${ESDC_VER#v}"
UPG_DIR="${UPGRADE_DIR:-"/opt/upgrade"}"
FINISHED_SUCCESSFULLY=0

# *** START ***

printmsg "Verifying current installation"

if [[ -a "${UPG_DIR}" ]]; then
	die 1 "Upgrade dir (${UPG_DIR}) exists. Please remove it first."
fi

if ! mount_usb_key; then
	die 2 "Failed to mount USB key. Aborting."
fi

USBMNT="$(_usbkey_get_mountpoint)"
USB_DEV="$(_usbkey_get_device)"
USB_VERSION_FILE="${USBMNT}/version"

if [[ -z "${USB_DEV}" ]]; then
	die 2 "ESDC USB key not found. Aborting."
fi

printmsg "Found USB device: ${USB_DEV}"

if ! [[ -f "${USB_VERSION_FILE}" ]]; then
	umount_usb_key || true
	die 3 "Invalid or unknown USB key format. Aborting upgrade."
fi

# shellcheck disable=SC2002
CURR_USB_VER="$(cat "${USB_VERSION_FILE}" | sed -e 's/^esdc-.e-.n-//')"
# shellcheck disable=SC2002
WANTED_USB_IMG_VARIANT="$(cat "${USB_VERSION_FILE}" | sed -re 's/^(esdc-.e-.n-).*/\1/')"
if [[ ${FORCE} -ne 1 ]] && [[ "${CURR_USB_VER}" == "${NEW_USB_VER}" ]]; then
	umount_usb_key || true
	die 0 "Requested ESDC version is already on the USB key. Nothing to do."
fi

umount_usb_key

printmsg "Downloading new USB image"
ESDC_IMG="${WANTED_USB_IMG_VARIANT}${NEW_USB_VER}.img"
ESDC_IMG_FULL="${UPG_DIR}/${ESDC_IMG}"
ESDC_DOWNLOAD_URL="https://download.erigones.org/esdc/usb/stable/${ESDC_IMG}.gz"

trap cleanup EXIT

printmsg "Download URL: ${ESDC_DOWNLOAD_URL}"
mkdir -p "${UPG_DIR}"

# shellcheck disable=SC2086
if ! ${CURL} ${CURL_QUIET} ${CURL_DEFAULT_OPTS} -o "${ESDC_IMG_FULL}.gz" "${ESDC_DOWNLOAD_URL}"; then
	die 5 "Cannot download new USB image archive. Please check your internet connection."
fi

printmsg "Unpacking new USB image"
${GZIP} -d "${ESDC_IMG_FULL}.gz"

# change trailing p1 for p0 (c1t1d0p1 -> c1t1d0p0)
USB_DEV_P0="${USB_DEV/p1*}p0"

# confirmation
printmsg "Going to write ${ESDC_IMG} image to USB device: ${USB_DEV_P0}"
printmsg "This will overwrite the whole the USB device!"

if [[ "${YES}" -ne 1 ]]; then
	read -p "*** Are you sure you want to continue? [y/N] " -n 1 -r confirm
	echo
	if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
		die 10 "Aborted by user."
	fi
fi

# start upgrade
printmsg "Writing new image to the USB device: ${USB_DEV_P0}"
${DD} if="${ESDC_IMG_FULL}" of="${USB_DEV_P0}" bs=16M

printmsg "Mounting newly written USB key into ${USBMNT}"
# mount exactly the same dev that was written to
${MOUNT} -F pcfs -o foldcase,noatime "${USB_DEV}" "${USBMNT}"

printmsg "Verifying newly written USB key"
# shellcheck disable=SC2002
CURR_USB_VER="$(cat "${USB_VERSION_FILE}" | sed -e 's/^esdc-.e-.n-//')"
printmsg "ESDC version on USB: ${CURR_USB_VER}"
umount_usb_key || true

FINISHED_SUCCESSFULLY=1

printmsg "Upgrade completed successfully"
printmsg "Please reboot to load new platform"

