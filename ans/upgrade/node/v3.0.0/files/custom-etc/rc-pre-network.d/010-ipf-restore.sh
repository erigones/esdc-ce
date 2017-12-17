#!/bin/bash
#
# This script generates firewall rules from files
# stored (most likely in) /opt/custom/etc/ipf.d
# It searches for files starting with the name
# of the respective conf file, e.g. for ipf.conf
# It matches either ipf.conf or ipf.conf-001, etc.
#
# It is intended for two things:
# 1. restore fw config from a permanent storage
# 2. split the fw config into multiple files
#
# Recommended format is <confname>-NNN
# Examples: 
# ipf.conf-005 ipf.conf-010 ...
# ipnat.conf-005 ipnat.conf-010 ...
# ipf6.conf-005 ipf6.conf-010 ...
#
# If no matching files exist, the firewall
# config is not touched.
#

RULES_DIR="/opt/custom/etc/ipf.d"
GENERATE_FILES="ipf.conf ipnat.conf ipf6.conf"
OUTPUT_DIR="/etc/ipf"
IPF_SERVICE="svc:/network/ipfilter:default"

set -e

. /lib/svc/share/smf_include.sh

update_fw() {
	if [[ ! -d "${RULES_DIR}" ]]; then
		# nothing to do
		exit $SMF_EXIT_OK
	fi

	FW_MODIFIED=0
	for cfgfile in ${GENERATE_FILES}; do
		# get list of all conf files in RULES_DIR
		# that end with requested filename (e.g. ipf.conf*)
		# and sort them by name before merging
		set +e
		# 'ls' does better job here than shell sort (like 'cat *')
		CONF_LIST="$(ls -1 ${RULES_DIR}/${cfgfile}* 2> /dev/null)"
		set -e

		if [[ -z "${CONF_LIST}" ]]; then
			# nothing to do
			continue
		fi

		echo "Generating firewall rules for ${cfgfile}"
		echo "${CONF_LIST}" | xargs cat > "${OUTPUT_DIR}/${cfgfile}"
		FW_MODIFIED=1
	done

	if [[ ${FW_MODIFIED} -eq 1 ]]; then
		# refresh firewall if applicable
		if [[ "$(/usr/bin/svcs -Ho state ${IPF_SERVICE})" == "online" ]]; then
			/usr/sbin/svcadm refresh "${IPF_SERVICE}"
		elif [[ "$(/usr/bin/svcs -Ho state ${IPF_SERVICE})" == "maintenance" ]]; then
			/usr/sbin/svcadm clear "${IPF_SERVICE}"
		fi
	else
		# clear maintenance if necessary
		if [[ "$(/usr/bin/svcs -Ho state ${IPF_SERVICE})" == "maintenance" ]]; then
			/usr/sbin/svcadm clear "${IPF_SERVICE}"
		fi
	fi
}


case "$1" in
	start)
		update_fw
		;;
	stop)
		exit $SMF_EXIT_OK
		;;
	refresh)
		update_fw
		;;
	*)
		echo "Usage: $0 {start|stop|refresh}"
		exit $SMF_EXIT_ERR_CONFIG
esac

exit $SMF_EXIT_OK

