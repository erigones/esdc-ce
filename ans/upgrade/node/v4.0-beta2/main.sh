#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

echo "+ Updating 020-ipsec-restore.sh"
cp -f "${VERSION_DIR}/files/020-ipsec-restore.sh" "/opt/custom/etc/rc-pre-network.d/020-ipsec-restore.sh"
chmod +x "/opt/custom/etc/rc-pre-network.d/020-ipsec-restore.sh"

#
# https://github.com/erigones/esdc-factory/pull/128
#
echo "+ Updating /opt/custom/smf/zabbix-agent.xml"
cat "${VERSION_DIR}/files/zabbix-agent.xml" > "/opt/custom/smf/zabbix-agent.xml"
# when OS is installed on disk, the SMF DB is permanent and needs explicit import:
/usr/sbin/svccfg import "/opt/custom/smf/zabbix-agent.xml"
