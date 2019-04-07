#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-ce/issues/375
#
echo "+ Updating /opt/zabbix/etc/scripts/vm-cpu-monitor"
cat "${VERSION_DIR}/files/monitoring/vm-cpu-monitor" > "/opt/zabbix/etc/scripts/vm-cpu-monitor"
svcadm restart svc:/application/zabbix/vm-cpu-monitor
