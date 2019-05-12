#!/bin/bash
#
# This script sets MTU according to SmartOS mdata network settings.
# It is needed because KVM's integrated DHCP server does not
# send MTU value. As a consequence (especially in overlay
# networks), the MTU is set to default 1500 which might be
# suboptimal or might even prevent proper communication.

# The MTU override is set only if it differs from the
# expected value, leaving space for possible future fixes
# or external DHCP server. It is also bhyve-friendly
# (because bhyve uses cloud-init and sets MTU correctly).
#
# This script runs after cloud-init and network-start.
#

JQ="/usr/bin/jq"

IF_PREFIX="$(ifconfig -a | grep -E '^eth|^net' | head -1 | cut -c 1-3)"
NICINFO="$(/usr/sbin/mdata-get sdc:nics)"

if [[ -z "${NICINFO}" ]] || [[ -z "${IF_PREFIX}" ]]; then
    exit 0
fi

if [[ ! -x "${JQ}" ]]; then
    echo "Binary 'jq' is missing! Aborting MTU setup."
    exit 1
fi

nicnum=0
while read -r mtu; do
    ifname="${IF_PREFIX}${nicnum}"
    cfgline="supersede interface-mtu ${mtu};"
    cfgfile="/etc/dhcp/dhclient-${ifname}.conf"

    if [[ "${mtu}" -ne 1500 ]]; then
        # this is the main reason of this script
        if [[ "$(cat "/sys/class/net/${ifname}/mtu")" != "${mtu}" ]]; then
            # MTU is set differently from what it should be
            # set it to correct value
            echo "$0: Overriding ${ifname} MTU to ${mtu}"
            /usr/sbin/ip link set mtu "${mtu}" dev "${ifname}"

            # persist cfg
            if [[ ! -f "${cfgfile}" ]]; then
                echo "${cfgline}" > "${cfgfile}"
            elif ! grep -q "${cfgline}" "${cfgfile}"; then
                # file exists and has different MTU setting...
                # do the cfg merge
                grep -v "^supersede interface-mtu" "${cfgfile}" > "${cfgfile}.tmp"
                echo "${cfgline}" >> "${cfgfile}.tmp"
                mv -f "${cfgfile}.tmp" "${cfgfile}"
            fi
        fi
    else
        # MTU is standard 1500, remove conf param override
        # in case the interfaces have changed
        if [[ -f "${cfgfile}" ]]; then
            echo "$0: Removing MTU override for ${ifname}"
            grep -v "^supersede interface-mtu" "${cfgfile}" > "${cfgfile}.tmp"
            mv -f "${cfgfile}.tmp" "${cfgfile}"
        fi
    fi

    ((nicnum++))
done <<< "$("${JQ}" ".[].mtu" <<< "${NICINFO}")"
