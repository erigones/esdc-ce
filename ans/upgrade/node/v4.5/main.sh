#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-ce/issues/524
#
echo "+ Add bhyve disk I/O monitoring daemon"
for file in bhiostat vm-bhyve-disk-io-monitor vm-disk-discovery; do
	cp -a "${VERSION_DIR}/files/${file}" "/opt/zabbix/etc/scripts/${file}"
done

for file in zabbix-vm-disk-io-bhyve.xml; do
	cp -a "${VERSION_DIR}/files/${file}" "/opt/custom/smf/${file}"
	# when OS is installed on disk, the SMF DB is permanent and needs explicit import:
	/usr/sbin/svccfg import "/opt/custom/smf/${file}"
done



