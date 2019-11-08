#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# Errata of
# https://github.com/erigones/esdc-ce/issues/450
#
echo "+ Updating /usbkey/scripts/*usb* scripts"
rm -f "/opt/custom/smf/mount-usb.sh" "/opt/custom/smf/umount-usb.sh"
cat "${ERIGONES_HOME}/bin/mount-esdc-usb" > "/usbkey/scripts/mount-usb.sh"
cat "${ERIGONES_HOME}/bin/umount-esdc-usb" > "/usbkey/scripts/umount-usb.sh"
chmod 755 "/usbkey/scripts/mount-usb.sh" "/usbkey/scripts/umount-usb.sh"

