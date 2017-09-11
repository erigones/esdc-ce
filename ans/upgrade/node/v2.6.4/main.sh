#!/bin/bash

set -e

#
# https://github.com/erigones/esdc-ce/issues/244
#
VM_IMG01="2b504f53-1c0b-4ceb-bfda-352f549a70e1"

if [[ -z "$(vmadm list -p uuid="${VM_IMG01}")" ]]; then
	exit 0  # img01 is not present on this node
fi

echo "+ Installing missing service images"
VM_IMG01_ZPOOL="$(vmadm get "${VM_IMG01}" | json zpool)"
VM_IMG01_DATASETS="/${VM_IMG01_ZPOOL}/${VM_IMG01}/root/datasets"
USBKEY_DATASETS="/usbkey/datasets"
SHIPMENT_UID=10000  # See bin/esimg
SHIPMENT_GID=10000

if [[ ! -d "${VM_IMG01_DATASETS}" ]] || [[ ! -d "${USBKEY_DATASETS}" ]] ; then
	exit 0  # img01 or usbkey datasets directory does not exist
fi

for img_manifest in "${USBKEY_DATASETS}"/*.imgmanifest; do
	img_uuid="$(json < "${img_manifest}" "uuid")"
	img_dir="${VM_IMG01_DATASETS}/${img_uuid}"
	img_file="${USBKEY_DATASETS}/$(basename "${img_manifest}" .imgmanifest).zfs.gz"

	if [[ ! -d "${img_dir}" ]] && [[ -f "${img_file}" ]]; then
		mkdir "${img_dir}"
		cp "${img_file}" "${img_dir}/file"
		cp "${img_manifest}" "${img_dir}/manifest"
		chown -R ${SHIPMENT_UID}:${SHIPMENT_GID} "${img_dir}"
		chmod 0755 "${img_dir}"
		chmod 0644 "${img_dir}"/*
	fi
done
