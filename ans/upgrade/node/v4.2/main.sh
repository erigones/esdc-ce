#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-ce/issues/446
#
echo "+ Updating Zabbix agent helpers"
for file in zabbix-vm-cpu-monitor.xml zabbix-vm-disk-io-kvm.xml zabbix-vm-network-monitor.xml; do
	cat "${VERSION_DIR}/files/${file}" > "/opt/custom/smf/${file}"
	# when OS is installed on disk, the SMF DB is permanent and needs explicit import:
	/usr/sbin/svccfg import "/opt/custom/smf/${file}"
done
svcadm restart svc:/application/zabbix/vm-network-monitor:default \
	svc:/application/zabbix/vm-kvm-disk-io-monitor:default \
	svc:/application/zabbix/vm-cpu-monitor:default

#
# https://smartos.org/bugview/OS-7662
# https://github.com/erigones/esdc-ce/issues/453
#
if ! grep -q '^smt_enabled=' /usbkey/config; then
	print '\nsmt_enabled=true\n' >> /usbkey/config
fi
