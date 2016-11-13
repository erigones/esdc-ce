#!/usr/bin/env bash
#
# functions.sh - Erigones common functions library
#

###############################################################
# Globals
###############################################################
#
# Paths
export ERIGONES_HOME=${ERIGONES_HOME:-"/opt/erigones"}
export PYTHONPATH=${PYTHONPATH:-"${ERIGONES_HOME}:${ERIGONES_HOME}/envs/lib/python2.7/site-packages"}
export PATH="${ERIGONES_HOME}/bin:/usr/bin:/usr/sbin:/opt/local/bin:/opt/local/sbin:/opt/local/gcc47/bin:/usr/local/bin:/usr/local/sbin:/bin:/sbin"

# Exit codes
declare -ri _ERR_INPUT=1
declare -ri _ERR_UNKNOWN=99

#
# Global variables
declare -A LOCKS
declare -i LOCK_MAX_WAIT=30
declare -r SERVICE_DIR="/opt/custom/smf"

#
# Binaries
ZFS=${ZFS:-"/usr/sbin/zfs"}
SSH=${SSH:-"/usr/bin/ssh"}
GZIP=${GZIP:-"/usr/bin/gzip"}
BZIP2=${BZIP2:-"/usr/bin/bzip2"}
DIGEST=${DIGEST:-"/usr/bin/digest -a sha1"}
DATE=${DATE:-"/usr/bin/date"}
STAT=${STAT:-"/usr/bin/stat"}
RM=${RM:-"/usr/bin/rm"}
CAT=${CAT:-"/usr/bin/cat"}
AWK=${AWK:-"/usr/bin/awk"}
SED=${SED:-"/usr/bin/sed"}
MKDIR=${MKDIR:-"/usr/bin/mkdir -p"}
MBUFFER=${MBUFFER:-"${ERIGONES_HOME}/bin/mbuffer"}
JSON=${JSON:-"/usr/bin/json"}
SVCS=${SVCS:-"/usr/bin/svcs"}
SVCADM=${SVCADM:-"/usr/sbin/svcadm"}
SVCCFG=${SVCCFG:-"/usr/sbin/svccfg"}
ZONEADM=${ZONEADM:-"/usr/sbin/zoneadm"}
ZONECFG=${ZONECFG:-"/usr/sbin/zonecfg"}
VMADM=${VMADM:-"/usr/sbin/vmadm"}
IMGADM=${IMGADM:-"/usr/sbin/imgadm"}
BC=${BC:-"/usr/bin/bc"}
QGA=${QGA:-"${ERIGONES_HOME}/bin/qga-client"}
QGA_SNAPSHOT=${QGA_SNAPSHOT:-"${ERIGONES_HOME}/bin/qga-snapshot"}

###############################################################
# Arguments passed to ssh
###############################################################
# NOTICE:
# If we use SunSSH, we can use arcfour safely. If we use OpenSSH
# >6.7, we have to explicitly enable arcfour, because it's disabled
# by default
###############################################################
SSH_ARGS=${SSH_ARGS:-"-c arcfour256 -o BatchMode=yes -o StrictHostKeyChecking=no "}

###############################################################
# Arguments passed to mbuffer
###############################################################
MBUFFER_ARGS=${MBUFFER_ARGS:-"-s 128k -m 128M -q -v0 -e -W 300 "}


###############################################################
# General helper functions
###############################################################

die() {
	local exit_code=$1
	shift
	local msg=$*

	[[ ! -z "${msg}" ]] && echo "ERROR: ${msg}" 1>&2
	[[ -z "${exit_code}" ]] && exit_code=${_ERR_UNKNOWN}

	exit "${exit_code}"
}

get_hostname() {
	hostname
}

get_timestamp() {
	${DATE} '+%s'
}

checksum() {
	local filename="$1"

	${DIGEST} "${filename}"
}

get_file_size() {
	local filename="$1"

	${STAT} --format='%s' "${filename}"
}

startswith() {
	local string="$1"
	local start="$2"

	[[ "${string}" == "${start}"* ]]
}

trim() {
	local string="$1"

	string="${string#"${string%%[![:space:]]*}"}"
	string="${string%"${string##*[![:space:]]}"}"

	echo -n "${string}"
}

join() {
	local separator="$1"
	shift
	local array=("$@")

	regex="$(printf "${separator}%s" "${array[@]}")"
	regex="${regex:${#separator}}" # remove leading separator

	echo "${regex}"
}

run_ssh() {
	# shellcheck disable=SC2086
	${SSH} ${SSH_ARGS} "$@"
}

test_ssh() {
	local host="$1"
	local user="${2:-"root"}"

	run_ssh -o ConnectTimeout=10 "${user}@${host}" "true" &> /dev/null
}

test_ssh_hostname() {
	local host="$1"
	local user="${2:-"root"}"

	run_ssh -o ConnectTimeout=10 "${user}@${host}" "hostname"
}

run_mbuffer() {
	# shellcheck disable=SC2086
	${MBUFFER} ${MBUFFER_ARGS} "$@"
}

calculate() {
	local math_expr="${1}"

	echo "${math_expr}" | "${BC}"
}

round() {
	local number="${1}"
	local -i places="${2:-0}"

	printf "%.${places}f" "${number}"
}


###############################################################
# Validators (motto: die as soon as possible)
###############################################################

validate_uuid() {  
	local uuid="$1"
	local re_uuid='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

	[[ "${#uuid}" == "36" && "${uuid}" =~ ${re_uuid} ]] && return 0

	die ${_ERR_INPUT} "Invalid uuid"
}

validate_ascii() {
	local str="$1"
	local err="$2"
	local re_ascii='^[0-9a-zA-Z:_\.-]+$'

	[[ -n "${str}" && "${str}" =~ ${re_ascii} ]] || die ${_ERR_INPUT} "${err}"
}


###############################################################
# ZFS helper functions
###############################################################

_zfs_snap() {
	local snapshot="$1"
	local metadata="${2:-"null"}"
	local fsfreeze="${3:-}"  # path to QA socket
	local -i rc

	if [[ -z "${fsfreeze}" ]]; then
		if [[ "${metadata}" == "null" ]]; then
			${ZFS} snapshot "${snapshot}"
		else
			${ZFS} snapshot -o "${metadata}" "${snapshot}"
		fi
	else
		if [[ "${metadata}" == "null" ]]; then
			${QGA_SNAPSHOT} "${fsfreeze}" "${snapshot}"
		else
			${QGA_SNAPSHOT} "${fsfreeze}" "${snapshot}" "${metadata}"
		fi
	fi
}

_zfs_destroy() {
	local item="$1"
	local force="${2:-}"

	if [[ "${force}" == "true" ]]; then
		${ZFS} destroy -rRf "${item}"
	else
		${ZFS} destroy "${item}"
	fi
}

_zfs_destroy_snapshots() {
	local dataset="$1"

	${ZFS} destroy "${dataset}@%"
}

_zfs_rollback() {
	local snapshot="$1"

	${ZFS} rollback -r "${snapshot}"
}

_zfs_send_size() {
	local snapshot_target="$1"  # last (target) dataset@snapshot
	local snapshot_source="${2:-}"  # previous (source) snapshot without dataset

	if [[ -z "${snapshot_source}" ]]; then
		# shellcheck disable=SC2016
		${ZFS} send -Pnv "${snapshot_target}" 2>&1 | tail -n 1 | "${AWK}" '{ print $2 }'
	else
		# shellcheck disable=SC2016
		${ZFS} send -Pnvi "${snapshot_source}" "${snapshot_target}" 2>&1 | tail -n 1 | "${AWK}" '{ print $2 }'
	fi
}

_zfs_send() {
	local snapshot="$1"

	${ZFS} send "${snapshot}"
}

_zfs_send_incr() {
	local snapshot1="$1"
	local snapshot2="$2"

	${ZFS} send -i "${snapshot1}" "${snapshot2}"
}

_zfs_recv() {
	local dataset="$1"
	local force="${2:-}"

	if [[ "${force}" == "true" ]]; then
		${ZFS} receive -F "${dataset}"
	else
		${ZFS} receive "${dataset}"
	fi
}

_zfs_snapshot_exists() {
	local snapshot="$1"

	"${ZFS}" list -t snapshot -o name "${snapshot}"
}

_zfs_dataset_exists() {
	local dataset="$1"

	"${ZFS}" list -o name "${dataset}"
}

_zfs_dataset_property() {
	local dataset="$1"
	local property="$2"

	${ZFS} get -H -p -o value "${property}" "${dataset}"
}

_zfs_set_dataset_property() {
	local dataset="$1"
	local name="$2"
	local value="$3"

	${ZFS} set "${name}"="${value}" "${dataset}"
}

_zfs_set_dataset_property_children() {
	local dataset="$1"
	local name="$2"
	local value="$3"
	local ds

	${ZFS} list -H -p -o name -t filesystem,volume -r "${dataset}" | while read ds; do
		[[ "${ds}" == "${dataset}" ]] && continue

		_zfs_set_dataset_property "${ds}" "${name}" "${value}"
	done
}

_zfs_clear_dataset_property() {
	local dataset="$1"
	local name="$2"

	${ZFS} inherit "${name}" "${dataset}"
}

_zfs_dataset_properties() {
	local dataset="$1"
	local properties="$2"

	${ZFS} get -H -p -o property,value "${properties}" "${dataset}"
}

_zfs_list_snapshots() {
	local dataset="$1"
	local properties="${2-"name"}"

	${ZFS} list -t snapshot -H -p -o "${properties}" -r -d 1 "${dataset}"
}

_zfs_list_snapshots_zpool() {
	local pool="$1"
	local properties="${2-"name"}"

	${ZFS} list -t snapshot -H -p -o "${properties}" -r "${pool}"
}

_zfs_dataset_rename() {
	local cur_dataset="$1"
	local new_dataset="$2"
	local set_zoned="${3:-}"
	local -i rc

	${ZFS} rename -f "${cur_dataset}" "${new_dataset}"
	rc=$?

	if [[ ${rc} -eq 0 && "${set_zoned}" == "true" ]]; then
		_zfs_set_dataset_property "${new_dataset}" zoned on
	fi

	return ${rc}
}

_zfs_dataset_create() {
	local dataset="$1"
	local ds_type="$2"  # filesystem or volsize
	shift 2
	local -a properties=("$@")
	local -a params=()
	local prop

	for prop in "${properties[@]}"; do
		params+=("-o")
		params+=("${prop}")
	done

	if [[ ${ds_type} == "filesystem" ]]; then
		# shellcheck disable=SC2086
		${ZFS} create ${params[*]} "${dataset}"
	else
		# shellcheck disable=SC2086
		${ZFS} create ${params[*]} -V "${ds_type}" "${dataset}"
	fi
}

_zfs_rename_children() {
	local src_dataset="$1"
	local dst_dataset="$2"
	local set_zoned="${3:-}"
	local ds
	local ds_child

	${ZFS} list -H -p -o name -t filesystem,volume -r "${src_dataset}" | while read ds; do
		[[ "${ds}" == "${src_dataset}" ]] && continue

		ds_child="${ds#$src_dataset}"  # the expression will strip the src_dataset from the beginning of ds

		if [[ -n "${ds_child}" ]]; then
			_zfs_dataset_rename "${ds}" "${dst_dataset}${ds_child}"

			if [[ $? -eq 0 && "${set_zoned}" == "true" ]]; then
				_zfs_set_dataset_property "${dst_dataset}${ds_child}" zoned on
			fi
		fi
	done
}

_zfs_mount() {
	local dataset="$1"

	${ZFS} mount "${dataset}"
}

_zfs_unmount() {
	local dataset="$1"
	local force="${2:-}"

	if [[ "${force}" == "true" ]]; then
		${ZFS} unmount -f "${dataset}"
	else
		${ZFS} unmount "${dataset}"
	fi
}


###############################################################
# vmadm helper functions
###############################################################

_vm_status() {
	local uuid="$1"

	${VMADM} list -H -o state uuid="${uuid}"
}

_vm_start() {
	local uuid="$1"

	${VMADM} start "${uuid}" 2>&1
}

_vm_stop() {
	local uuid="$1"

	${VMADM} stop "${uuid}" 2>&1
}

_vm_stop_force() {
	local uuid="$1"

	${VMADM} stop "${uuid}" -F 2>&1
}

_vm_destroy() {
	local uuid="$1"

	${VMADM} destroy "${uuid}" 2>&1
}

_vm_json() {
	local uuid="$1"

	${VMADM} get "${uuid}"
}

_vm_create() {
	# VM json on stdin

	${VMADM} create
}

_vm_delete() {
	local uuid="$1"

	${VMADM} delete "${uuid}"
}

_vm_property() {
	local json="$1"
	local property="$2"
	local value
	value=$(echo "${json}" | "${JSON}" "${property}")

	[[ -z "${value}" ]] && return 1

	echo "${value}"

	return 0
}

_vm_brand() {
	local json="$1"

	echo "${json}" | "${JSON}" "brand"
}

_vm_zfs_filesystem() {
	local json="$1"

	echo "${json}" | "${JSON}" "zfs_filesystem"
}

_zone_create() {
	local zonename="$1"
	local zonepath="$2"

	${ZONECFG} -z "${zonename}" create -a "${zonepath}"
}

_zone_delete() {
	local zonename="$1"

	${ZONECFG} -z "${zonename}" delete -F
}

_zone_attach() {
	local zone="$1"

	${ZONEADM} -z "${zone}" attach
}

_zone_detach() {
	local zone="$1"

	${ZONEADM} -z "${zone}" detach
}

_vmadmd_restart() {
	${SVCADM} restart vmadmd
}

_image_exists() {
	local image_uuid="$1"
	local pool="$2"

	${IMGADM} get -P "${pool}" "${image_uuid}" &> /dev/null
}

_vm_qga_lock() {
	local qga_sock="$1"
	local lockfile="${qga_sock}.lock"
	local -i waited=0

	while [[ ${waited} -lt ${LOCK_MAX_WAIT} ]]; do
		if [[ ! -f "${lockfile}" ]]; then
			echo $$ > "${lockfile}" && return 0
		fi
		sleep 1
		((waited++))
	done

	echo "Could not acquire Qemu Guest Agent socket lock" >&2

	return 1
}

_vm_qga_unlock() {
	local qga_sock="$1"
	local lockfile="${qga_sock}.lock"

	if [[ -f "${lockfile}" ]]; then
		if [[ "$(cat "${lockfile}")" == "$$" ]]; then
			rm -f "${lockfile}"
		else
			echo "Qemu Guest Agent socket lock mismatch during unlock!" >&2
			return 1
		fi
	fi

	return 0
}

_vm_qga_cmd() {
	local qga_sock="$1"
	shift

	${QGA} "${qga_sock}" "$@"
}

_vm_qga_fsfreeze_freeze() {
	local qga_sock="$1"
	local -i rc=0
	local ret=""

	if [[ -S "${qga_sock}" ]]; then
		ret=$(_vm_qga_lock "${qga_sock}" && _vm_qga_cmd "${qga_sock}" fsfreeze freeze 2>&1)
		rc=$?

		if [[ ${rc} -eq 0 ]]; then
			LOCKS["fsfreeze:${qga_sock}"]=1  # Lock now, because we want _vm_qga_fsfreeze_fsthaw() to run

			# check if return value is greater than 0 (number of FS freezed)
			[[ "${ret}" =~ ^-?[0-9]+$ && ${ret} -gt 0 ]] && return 0

			rc=1
		fi

		echo "Filesystem freeze failed (${ret})" >&2
	fi

	return ${rc}
}

_vm_qga_fsfreeze_fsthaw() {
	local qga_sock="$1"
	local -i rc=0
	local ret=""

	if [[ -n ${LOCKS["fsfreeze:${qga_sock}"]:-} ]]; then
		unset LOCKS["fsfreeze:${qga_sock}"]  # Remove lock now

		if [[ -S "${qga_sock}" ]]; then
			ret=$(_vm_qga_cmd "${qga_sock}" fsfreeze thaw 2>&1)

			if [[ ${rc} -eq 0 ]]; then
				# check if return value is greater or equal than 0 (number of FS thawed)
				[[ "${ret}" =~ ^-?[0-9]+$ && ${ret} -ge 0 ]] && return 0

				rc=1
			fi

			echo "Filesystem thaw failed (${ret})" >&2
		fi
	fi

	_vm_qga_unlock "${qga_sock}"

	return ${rc}
}


###############################################################
# SMF helper functions
###############################################################

_parse_service_name() {
	local fmri="$1"
    local service_instance="${fmri##*/}"

	echo "${service_instance%%:*}"
}

_service_file_save() {
	local fmri="$1"
	local service="$(_parse_service_name "${fmri}")"

	_service_export "${fmri}" > "${SERVICE_DIR}/${service}.xml"
}

_service_file_remove() {
	local fmri="$1"
	local service="$(_parse_service_name "${fmri}")"

	rm -f "${SERVICE_DIR}/${service}.xml"
}

_service_status() {
	local fmri="$1"
	local columns="${2-"state"}"

	${SVCS} -H -o "${columns}" "${fmri}"
}

_service_disable() {
	local fmri="$1"

	${SVCADM} disable -s "${fmri}" && _service_file_save "${fmri}"
}

_service_enable() {
	local fmri="$1"

	${SVCADM} enable -s "${fmri}" && _service_file_save "${fmri}"
}

_service_restart() {
	local fmri="$1"

	${SVCADM} restart "${fmri}"
}

_service_validate() {
	local file="$1"

	${SVCCFG} validate "${file}"
}

_service_export() {
	local fmri="$1"

	${SVCCFG} export "${fmri}"
}

_service_import() {
	local fmri="$1"
	local file="$2"

	${SVCCFG} import "${file}" && _service_file_save "${fmri}"
}

_service_delete() {
	local fmri="$1"

	${SVCCFG} delete "${fmri}" && _service_file_remove "${fmri}"
}

_service_instance_import() {
	local fmri="$1"
	local file="$2"

	${SVCCFG} -s "${fmri}" import "${file}" && _service_file_save "${fmri}"
}

_service_instance_delete() {
	local fmri="$1"
	local name="$2"

	${SVCCFG} -s "${fmri}" delete "${name}" && _service_file_save "${fmri}"
}
