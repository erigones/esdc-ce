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

# shellcheck disable=SC1090
. "${ERIGONES_HOME}"/bin/eslib/functions.sh


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

zfs_sync_quota() {
		local src_vol="$1"
		local dst_vol="$2"
		local host="$3"

		local src_quota
		local dst_quota

		src_quota="$(run_ssh "root@${host}" "${SELF}" _zfs_get_param "${src_vol}" quota)"
		dst_quota="$(_zfs_get_param "${dst_vol}" quota)"

		[[ -z "${src_quota}" ]] && src_quota="none"
		if [[ "${src_quota}" != "${dst_quota}" ]]; then
				_zfs_set_param "${dst_vol}" quota "${src_quota}"
		fi
}


###############################################################
# main
###############################################################
"$@"
exit $?
