#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-ce/issues/446
# (Clean installs were not fixed so check and re-run fix from previous version.)
#
if ! grep -q LD_LIBRARY_PATH /opt/custom/smf/zabbix-vm-network-monitor.xml; then
	"${VERSION_DIR}/../v4.2/main.sh"
fi
