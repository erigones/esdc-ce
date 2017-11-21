#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-factory/issues/89
#
CUSTOM_ETC="/opt/custom/etc"
SRC_CUSTOM_ETC="${VERSION_DIR}/files/custom-etc"

mkdir -p "${CUSTOM_ETC}"

for srcdir in "${SRC_CUSTOM_ETC}"/*; do
	dirname="$(basename "${dir}")"
	if [[ ! -e "${CUSTOM_ETC}/${dirname}" ]]; then
		echo "+ Placing ${dirname} into ${CUSTOM_ETC}"
		cp -a "${srcdir}" "${CUSTOM_ETC}"
	fi
done

