#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

# https://github.com/erigones/esdc-ce/issues/129
echo "+ Updating /opt/zabbix/etc/scripts/kstat"
cat "${VERSION_DIR}/files/kstat" > "/opt/zabbix/etc/scripts/kstat"

# https://github.com/erigones/esdc-ce/issues/183
echo "+ Updating /opt/zabbix/etc/scripts/dataset-discovery"
cat "${VERSION_DIR}/files/dataset-discovery" > "/opt/zabbix/etc/scripts/dataset-discovery"
echo "+ Updating /opt/zabbix/etc/scripts/vm-network-monitor"
cat "${VERSION_DIR}/files/vm-network-monitor" > "/opt/zabbix/etc/scripts/vm-network-monitor"
echo "+ Restarting svc:/application/zabbix/vm-network-monitor"
svcadm restart svc:/application/zabbix/vm-network-monitor

# https://github.com/erigones/esdc-ce/issues/179
# After /opt/custom/smf/erigonesd.xml is updated the user should do one of the two things:
#  - svccfg import /opt/custom/smf/erigonesd.xml (which will restart all erigonesd workers)
#  - or reboot the compute node
echo "+ Updating /opt/custom/smf/erigonesd.xml"
cat "${ERIGONES_HOME}/etc/init.d/erigonesd.xml" > /opt/custom/smf/erigonesd.xml
