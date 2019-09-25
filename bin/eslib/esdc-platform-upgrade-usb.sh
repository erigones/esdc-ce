#!/bin/bash

set -e

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
ESLIB="${ESLIB:-"${ERIGONES_HOME}/bin/eslib"}"

# shellcheck disable=SC1090
. "${ESLIB}/functions.sh"

ESDC_VER="${1}"
if [[ -z "${ESDC_VER}" ]]; then
	echo "Usage:   $0 <new_dc_version> [-v] [-f] [-y] [-u <usr:pwd>]"
	echo "Example: $0 v4.0"
	echo "Example: $0 /zones/esdc-ce-cn-4.1.img.gz"
	echo
	echo "Parameters:"
	echo "  -v                verbose download"
	echo "  -u <usr:pwd>      username and password required for accessing the enterprise edition download server"
	echo "  -f                force upgrade even when the requested version is already installed"
	echo "  -y                assume \"yes\" as default answer for all questions"

	exit 1
fi

LOCAL_UPGRADE=0
if [[ -f "${ESDC_VER}" ]] && [[ "${ESDC_VER}" =~ \.img\.gz$ ]]; then
	# upgrade from a local file
	# (the $ESDC_VER variable contains a valid filename)
	LOCAL_UPGRADE=1
elif ! [[ "${ESDC_VER}" =~ ^v[0-9]+\.[0-9]+ ]]; then
	die 2 "Unknown format of Danube Cloud version: ${ESDC_VER}"
fi

# process additional arguments
# curl: 15s conn T/O; allow redirects; 1000s max duration, fail on 404
CURL_DEFAULT_OPTS="--connect-timeout 15 -L --max-time 3600 -f"
CURL_QUIET="-s"
CURL_AUTH=""
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
		"-u")
			shift
			CURL_AUTH="${1}"
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

if ! mount_usb_key > /dev/null; then
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

if [[ "${LOCAL_UPGRADE}" -ne 1 ]]; then
	# shellcheck disable=SC2002
	WANTED_USB_IMG_VARIANT="$(cat "${USB_VERSION_FILE}" | sed -re 's/^(esdc-.e-.n-).*/\1/')"
	if [[ ${FORCE} -ne 1 ]] && [[ "${CURR_USB_VER}" == "${NEW_USB_VER}" ]]; then
		umount_usb_key
		die 0 "Requested ESDC version is already on the USB key. Nothing to do."
	fi

	printmsg "Downloading new USB image"
	ESDC_IMG="${WANTED_USB_IMG_VARIANT}${NEW_USB_VER}.img"
	ESDC_IMG_FULL="${UPG_DIR}/${ESDC_IMG}"

	if [[ "${WANTED_USB_IMG_VARIANT}" == *"-ee-"* ]]; then
		ESDC_DOWNLOAD_URL="https://download.erigones.com/esdc/usb/${ESDC_IMG}.gz"

		if [[ -z "${CURL_AUTH}" ]]; then
			read -p "*** Enter your enterprise edition download username: " -r curl_username
			read -p "*** Enter your enterprise edition download password: " -rs curl_password
			echo
			CURL_AUTH="${curl_username}:${curl_password}"
		fi
	else
		ESDC_DOWNLOAD_URL="https://download.erigones.org/esdc/usb/stable/${ESDC_IMG}.gz"
	fi

	if [[ -n "${CURL_AUTH}" ]]; then
		CURL_EXTRA_OPTS="-u ${CURL_AUTH}"
	fi

	printmsg "Download URL: ${ESDC_DOWNLOAD_URL}"
fi

umount_usb_key
mkdir -p "${UPG_DIR}"

trap cleanup EXIT

# remove reference to mounted partition so we target the whole disk
if [[ "${USB_DEV}" =~ s2$ ]]; then
	# change trailing s2 for p0 (c1t1d0s2 -> c1t1d0p0)
	# (GPT partition table)
	USB_DEV_P0="${USB_DEV/s2*}p0"
elif [[ "${USB_DEV}" =~ p1$ ]]; then
	# change trailing p1 for p0 (c1t1d0p1 -> c1t1d0p0)
	USB_DEV_P0="${USB_DEV/p1*}p0"
elif [[ "${USB_DEV}" =~ p0:1$ ]]; then
	# remove trailing :1 (c1t0d0p0:1 -> c1t0d0p0)
	USB_DEV_P0="${USB_DEV/:1*}"
else
	die 9 "Unrecognized partition specification: ${USB_DEV}"
fi

if [[ "${LOCAL_UPGRADE}" -eq 1 ]]; then
	ESDC_IMG_FULL="${UPG_DIR}/$(basename "${ESDC_VER/.gz}")"
	ESDC_IMG="${ESDC_IMG_FULL}"
# shellcheck disable=SC2086
elif ! ${CURL} ${CURL_QUIET} ${CURL_DEFAULT_OPTS} ${CURL_EXTRA_OPTS} -o "${ESDC_IMG_FULL}.gz" "${ESDC_DOWNLOAD_URL}"; then
	die 5 "Cannot download new USB image archive. Please check your internet connection."
fi

printmsg "Unpacking new USB image"
if [[ "${LOCAL_UPGRADE}" -ne 1 ]]; then
	${GZIP} -d "${ESDC_IMG_FULL}.gz"
else
	${GZIP} -dc "${ESDC_VER}" > "${ESDC_IMG_FULL}"
fi

# confirmation
printmsg "Going to write ${ESDC_IMG} image to USB device: ${USB_DEV_P0}"
printmsg "This will overwrite the whole USB device!"

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
if ! mount_usb_key > /dev/null; then
	die 2 "Failed to mount USB key. Upgrade failed."
fi

printmsg "Verifying newly written USB key"
# shellcheck disable=SC2002
CURR_USB_VER="$(cat "${USB_VERSION_FILE}" | sed -e 's/^esdc-.e-.n-//')"
printmsg "ESDC version on USB: ${CURR_USB_VER}"
umount_usb_key || true

FINISHED_SUCCESSFULLY=1

printmsg "Upgrade completed successfully"
printmsg "Please reboot to load new platform"

