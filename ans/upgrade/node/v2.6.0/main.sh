#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

echo "+ Updating /opt/zabbix/etc/scripts/kstat"
cat "${VERSION_DIR}/files/kstat" > "/opt/zabbix/etc/scripts/kstat"

# After /opt/custom/smf/erigonesd.xml is updated the user should do one of the two things:
#  - svccfg import /opt/custom/smf/erigonesd.xml (which will restart all erigonesd workers)
#  - or reboot the compute node
echo "+ Updating /opt/custom/smf/erigonesd.xml"
cat "${ERIGONES_HOME}/etc/init.d/erigonesd.xml" > /opt/custom/smf/erigonesd.xml
