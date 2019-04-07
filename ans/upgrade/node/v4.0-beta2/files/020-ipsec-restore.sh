#!/bin/bash
#
# This script restores IPSec config from files
# on permanent storage (most likely in
# /opt/custom/etc/ipsec). It overcomes the problem
# that most of the configuration in SmartOS is 
# non-persistent.
#
# If no IPSec files exist, the running config
# and IPSec services are not touched.
#

IPSEC_DIR="/opt/custom/etc/ipsec"

IKE_SERVICE="svc:/network/ipsec/ike:default"
IPSECINIT_SERVICE="svc:/network/ipsec/policy:default"

IKE_CONF_SRC="${IPSEC_DIR}/config"
IKE_CONF_DST="/etc/inet/ike/config"
IKE_PRESHARED_SRC="${IPSEC_DIR}/ike.preshared"
IKE_PRESHARED_DST="/etc/inet/secret/ike.preshared"

IPSECINIT_CONF_SRC="${IPSEC_DIR}/ipsecinit.conf"
IPSECINIT_CONF_DST="/etc/inet/ipsecinit.conf"


. /lib/svc/share/smf_include.sh

# returns 0 when file was updated and 1 if the update wasn't necessary
update_file() {
	local file_src="${1}"
	local file_dst="${2}"

	if [[ -f "${file_src}" ]] && ! cmp -s "${file_src}" "${file_dst}"; then
		echo "Updating ${file_src}"
		cp -a "${file_src}" "${file_dst}"
		return 0
	fi

	return 1
}

# return 0 if cleared
clear_maint() {
	local svc="${1}"
	local svc_state="$(/usr/bin/svcs -Ho state ${svc})"

	# clear maintenance if necessary
	if [[ "${svc_state}" == "maintenance" ]]; then
		/usr/sbin/svcadm clear "${svc}"
		return 0
	elif [[ "${svc_state}" == "disabled" ]]; then
		# by default ike service is disabled at boot
		/usr/sbin/svcadm enable "${svc}"
		return 0
	else
		return 1
	fi
}


reload_svc() {
	local svc="${1}"
	local svc_state="$(/usr/bin/svcs -Ho state ${svc})"

	# refresh or enable service if applicable
	if [[ "${svc_state}" == "disabled" ]]; then
		/usr/sbin/svcadm enable "${svc}"
	elif [[ "${svc_state}" == "online" ]]; then
		/usr/sbin/svcadm refresh "${svc}"
	else
		clear_maint "${svc}"
	fi
}

update_ipsec_conf() {
	if [[ ! -d "${IPSEC_DIR}" ]]; then
		# nothing to do
		exit $SMF_EXIT_OK
	fi

	update_file "${IKE_CONF_SRC}" "${IKE_CONF_DST}"
	rc1="${?}"
	update_file "${IKE_PRESHARED_SRC}" "${IKE_PRESHARED_DST}"
	rc2="${?}"
	if [[ "${rc1}" -eq 0 || "${rc2}" -eq 0 ]]; then
		# at least one file has been updated
		reload_svc "${IKE_SERVICE}"
	elif [[ -f "${IKE_CONF_DST}" ]]; then
		# config file exists, enable ike service
		clear_maint "${IKE_SERVICE}"
	fi


	if update_file "${IPSECINIT_CONF_SRC}" "${IPSECINIT_CONF_DST}"; then
		reload_svc "${IPSECINIT_SERVICE}"
	else
		clear_maint "${IPSECINIT_SERVICE}"
	fi
}


case "$1" in
	start)
		update_ipsec_conf
		;;
	stop)
		exit $SMF_EXIT_OK
		;;
	refresh)
		update_ipsec_conf
		;;
	*)
		echo "Usage: $0 {start|stop|refresh}"
		exit $SMF_EXIT_ERR_CONFIG
esac

exit $SMF_EXIT_OK

