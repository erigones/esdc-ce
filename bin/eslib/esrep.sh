#!/usr/bin/env bash
#
# esrep.sh - Erigones replication helper used by the esrep command
#
# Do not use this script manually! Use esrep instead.
#

set -u
set -o pipefail


###############################################################
# globals
###############################################################

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
SELF="${ERIGONES_HOME}/bin/eslib/esrep.sh"
#PROG="$(basename "$0")"

. "${ERIGONES_HOME}"/bin/eslib/functions.sh

declare MODE
declare -ri OK=0
declare -ri ERR_INPUT=1


###############################################################
# replication functions
###############################################################

_zfs_snapshot_send() {  # Used by zfs_send_recv()
	local snapshot="$1"
	local incr_snapshot="${2:-}"

	if [[ -n "${incr_snapshot}" ]]; then
		${ZFS} send -R -I "${incr_snapshot}" "${snapshot}"
	else
		${ZFS} send -R -p "${snapshot}"
	fi
}

zfs_send_recv() {
	local dataset="$1"
	local snapshot="$2"
	local host="$3"
	local incr_snapshot="${4:-}"
	local limit="${5:-}"

	[[ -n "${limit}" ]] && MBUFFER_ARGS+="-r ${limit} "

	if [[ -n "${incr_snapshot}" && "${incr_snapshot}" != "null" ]]; then
		run_ssh "root@${host}" "${SELF} _zfs_snapshot_send ${snapshot} ${incr_snapshot}" | run_mbuffer | _zfs_recv "${dataset}" "true"
	else
		run_ssh "root@${host}" "${SELF} _zfs_snapshot_send ${snapshot}" | run_mbuffer | _zfs_recv "${dataset}"
	fi
}


###############################################################
# main
###############################################################
"$@"
exit $?
