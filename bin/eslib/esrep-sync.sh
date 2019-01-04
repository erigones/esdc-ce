#!/usr/bin/env bash
#
# esrep-sync.sh - Erigones wrapper for running esrep sync loop from SMF
#
# Do not use this script manually! Use esrep instead.
#

trap "" SIGTERM

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
ESREP="${ERIGONES_HOME}/bin/esrep"
ALERT_ZABBIX_ITEM="alert3"
# Parameters look like this:
# sync -q -m %{{esrep/master}} -s %{{esrep/slave} ..
MASTER_UUID="$4"

out=$("${ESREP}" "$@")
e=$?

echo "${out}"

# Ignore OK and SIGTERM return code
if [[ ${e} -ne 0 && ${e} -ne 215 ]]; then
	detail=$(echo "${out}" | json msg 2> /dev/null)

	/opt/zabbix/bin/zabbix_sender -c /opt/zabbix/etc/zabbix_agentd.conf -s "${MASTER_UUID}" -k "${ALERT_ZABBIX_ITEM}" -o "${detail}"  > /dev/null
fi

exit ${e}
