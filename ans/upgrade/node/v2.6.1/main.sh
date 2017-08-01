#!/bin/bash

. /lib/svc/share/fs_include.sh

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

# https://github.com/erigones/esdc-ce/issues/207
echo "+ Uninstalling librabbitmq"
${ERIGONES_HOME}/bin/ctl.sh pip_uninstall librabbitmq --silence-errors

# https://github.com/erigones/esdc-factory/issues/65
BOOTED_FROM_HDD=0
mounted "/" "-" "zfs" < /etc/mnttab && BOOTED_FROM_HDD=1

if [[ "${BOOTED_FROM_HDD}" -eq 1 ]]; then
	echo "+ Creating /lib/svc/manifest/network/datalink-cleanup.xml"
	cat > "/lib/svc/manifest/network/datalink-cleanup.xml" <<EOF
<?xml version='1.0'?>
<!DOCTYPE service_bundle SYSTEM '/usr/share/lib/xml/dtd/service_bundle.dtd.1'>
<!--
 This is a simple script that cleans up persistent datalink configuration
 just after the system boots. This is only required for installation to HDD
 in order to support network/physical configuration from usbkey/config.
-->
<service_bundle type='manifest' name='datalink-cleanup'>
  <service name='network/datalink-cleanup' type='service' version='0'>
    <create_default_instance enabled='true'/>
    <single_instance/>
    <dependent name='datalink-management' restart_on='none' grouping='require_all'>
      <service_fmri value='svc:/network/datalink-management'/>
    </dependent>
    <exec_method name='start' type='method' exec='/bin/rm -f /etc/dladm/datalink.conf' timeout_seconds='10'/>
    <exec_method name='stop' type='method' exec=':true' timeout_seconds='3'/>
    <property_group name="startd" type="framework">
      <propval name="duration" type="astring" value="transient" />
      <propval name="ignore_error" type="astring" value="core,signal" />
    </property_group>
    <stability value='Unstable'/>
  </service>
</service_bundle>
EOF
fi
