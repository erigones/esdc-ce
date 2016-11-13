#!/usr/bin/env bash
#
# esbackup.sh - Erigones backup helper used by the esbackup command
#
# Do not use this script manually! Use esbackup instead.
#

set -u
set -o pipefail


###############################################################
# globals
###############################################################

ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
SELF="${ERIGONES_HOME}/bin/eslib/esbackup.sh"
#PROG="$(basename "$0")"

. "${ERIGONES_HOME}"/bin/eslib/functions.sh

declare MODE
declare -ri OK=0
declare -ri ERR_INPUT=1
declare -ri ERR_SNAPSHOT=2


###############################################################
# helper functions
###############################################################

_pack() {
	local algorithm="$1"
	local compressor

	case "${algorithm}" in
		gzip|gz)
			compressor="${GZIP} -c"
			;;
		bzip2|bz2)
			compressor="${BZIP2} -c"
			;;
		*)
			die ${ERR_INPUT} "Unsupported compression algorithm: ${algorithm}"
			;;
	esac

	${compressor}
}

_unpack() {
	local filename="$1"
	local algorithm="${filename##*.}"
	local uncompress

	case "${algorithm}" in
		gz)
			uncompress="${GZIP} -dc"
			;;
		bz2)
			uncompress="${BZIP2} -dc"
			;;
		zfs)
			uncompress="${CAT}"
			;;
		*)
			die ${ERR_INPUT} "Unsupported compression algorithm: ${algorithm}"
			;;
		esac

		${uncompress} "${filename}"
}


###############################################################
# dataset backup
###############################################################

_zfs_dataset_backup_send() {  # Used by zfs_dataset_backup_remote()
	local snapshot="$1"
	local incr_snapshot="${2:-}"

	if [[ -n "${incr_snapshot}" ]]; then
		_zfs_send_incr "${incr_snapshot}" "${snapshot}"
	else
		_zfs_send "${snapshot}"
	fi
}

zfs_dataset_backup_remote() {
	local dataset="$1"
	local snapshot="$2"
	local host="$3"
	local incr_snapshot="${4:-}"
	local limit="${5:-}"

	[[ -n "${limit}" ]] && MBUFFER_ARGS+="-r ${limit} "

	if [[ -n "${incr_snapshot}" && "${incr_snapshot}" != "null" ]]; then
		run_ssh "root@${host}" "${SELF} _zfs_dataset_backup_send ${snapshot} ${incr_snapshot}" | run_mbuffer | _zfs_recv "${dataset}" "true"
	else
		run_ssh "root@${host}" "${SELF} _zfs_dataset_backup_send ${snapshot}" | run_mbuffer | _zfs_recv "${dataset}"
	fi
}

zfs_dataset_backup_local() {
	local dataset="$1"
	local snapshot="$2"
	local incr_snapshot="${3:-}"
	local limit="${4:-}"

	[[ -n "${limit}" ]] && MBUFFER_ARGS+="-r ${limit} "

	if [[ -n "${incr_snapshot}" && "${incr_snapshot}" != "null" ]]; then
		_zfs_send_incr "${incr_snapshot}" "${snapshot}" | run_mbuffer | _zfs_recv "${dataset}" "true"
	else
		_zfs_send "${snapshot}"| run_mbuffer | _zfs_recv "${dataset}"
	fi
}

_zfs_dataset_restore_remote_recv() {  # Used by zfs_dataset_restore_remote() and zfs_file_restore_remote()
	local dataset="$1"

	run_mbuffer | _zfs_recv "${dataset}" "true"
}

zfs_dataset_restore_remote() {
	local snapshot="$1"
	local dataset="$2"
	local host="$3"

	_zfs_send "${snapshot}" | run_mbuffer | run_ssh "root@${host}" "${SELF} _zfs_dataset_restore_remote_recv ${dataset}"
}

zfs_dataset_restore_local() {
	local snapshot="$1"
	local dataset="$2"

	_zfs_send "${snapshot}" | _zfs_recv "${dataset}" "true"
}


###############################################################
# file backup
###############################################################

_zfs_file_backup_snapshot() {
	local dataset="$1"

	echo "${dataset}@backup-full-$(get_timestamp)"
}

_zfs_file_backup_send() {  # Used by zfs_file_backup_remote()
	local dataset="$1"
	local fsfreeze="${2:-}"
	local snapshot
	snapshot="$(_zfs_file_backup_snapshot "${dataset}")"

	_zfs_snap "${snapshot}" "${fsfreeze}" || die ${ERR_SNAPSHOT} "Failed to create backup snapshot"
	#shellcheck disable=SC2064
	trap "_zfs_destroy ${snapshot}" EXIT

	_zfs_send "${snapshot}"
}

zfs_file_backup_local() {
	local dataset="$1"
	local file="$2"
	local compression="${3:-"null"}"
	local limit="${4:-"null"}"
	local fsfreeze="${5:-}"
	local snapshot
	snapshot="$(_zfs_file_backup_snapshot "${dataset}")"

	[[ "${limit}" != "null" ]] && MBUFFER_ARGS+="-r ${limit} "

	_zfs_snap "${snapshot}" "${fsfreeze}" || die ${ERR_SNAPSHOT} "Failed to create backup snapshot"
	#shellcheck disable=SC2064
	trap "_zfs_destroy ${snapshot}" EXIT

	if [[ "${compression}" == "null" ]]; then
		_zfs_send "${snapshot}" | run_mbuffer -f -o "${file}"
	else
		_zfs_send "${snapshot}" | _pack "${compression}" | run_mbuffer -f -o "${file}"
	fi
}

zfs_file_backup_remote() {
	local dataset="$1"
	local file="$2"
	local host="$3"
	local compression="${4:-"null"}"
	local limit="${5:-"null"}"
	local fsfreeze="${6:-}"

	[[ "${limit}" != "null" ]] && MBUFFER_ARGS+="-r ${limit} "

	if [[ "${compression}" == "null" ]]; then
		run_ssh "root@${host}" "${SELF} _zfs_file_backup_send ${dataset} ${fsfreeze}" | run_mbuffer -f -o "${file}"
	else
		run_ssh "root@${host}" "${SELF} _zfs_file_backup_send ${dataset} ${fsfreeze}" | _pack "${compression}" | run_mbuffer -f -o "${file}"
	fi
}

zfs_file_restore_local() {
	local file="$1"
	local dataset="$2"

	_unpack "${file}" | _zfs_recv "${dataset}" "true"
}

zfs_file_restore_remote() {
	local file="$1"
	local dataset="$2"
	local host="$3"

	_unpack "${file}" | run_mbuffer | run_ssh "root@${host}" "${SELF} _zfs_dataset_restore_remote_recv ${dataset}"
}


###############################################################
# main
###############################################################
"$@"
exit $?
