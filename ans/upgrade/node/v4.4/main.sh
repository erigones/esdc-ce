#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-ce/issues/505
#
PKGIN_REPOS=/opt/local/etc/pkgin/repositories.conf
if grep -q erigones "${PKGIN_REPOS}"; then
	/usr/bin/sed -i '' -e 's;pkgsrc.erigones.org;pkgsrc.danube.cloud;' -e '/erigones/d' "${PKGIN_REPOS}"
fi
