#!/bin/bash

set -u

#######################################
# Basic code checks
#
# REQUIREMENTS: shellcheck (bash); jshint (JavaScript); flake8,radon (Python)
#######################################

MAINDIR="$(cd "$(dirname "$0")/.." || exit 128 ; pwd -P)"
ERIGONES_HOME=${ERIGONES_HOME:-"${MAINDIR}"}
export ERIGONES_HOME
cd "${ERIGONES_HOME}" || exit 64

#######################################
# Settings
SH_FOLDERS=("bin")
JS_FOLDERS=("gui/static/gui/js")
PY_FOLDERS=("ans" "api" "core" "gui" "pdns" "que" "sio" "vms")
RADON_MAX_CC=20
#######################################

# Parameters
CHECK_TYPE="${1:-"all"}"
shift
# shellcheck disable=SC2124
CHECK_FOLDERS="${@:-}"

# Colors
# shellcheck disable=SC1117
NC="\033[0m"
# shellcheck disable=SC1117
BOLD="\033[1m"
# shellcheck disable=SC1117
CYAN="\033[1;36m"
# shellcheck disable=SC1117
GREEN="\033[1;32m"
# shellcheck disable=SC1117
RED="\033[1;31m"
# Counters
ERROR_FILES=0
ERRORS=0
#######################################


printmsg() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${BOLD}${target}${NC}: ${msg}"
}

error() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${BOLD}${target}${NC}: ${RED}${msg}${NC}" >&2
}

success() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${BOLD}${target}${NC}: ${GREEN}${msg}${NC}"
}

_lint_shell_file() {
	local file="${1}"
	local rc=0
	local output
	local errors

	if ! head -n1 "${file}" | grep -q "bash"; then
		echo "${file}: not using bash (shebang check)"
		rc=1
		((ERRORS++))
	fi

	# shellcheck disable=SC1117
	if grep -qE "^\ \ *(echo|exit|return)" "${file}"; then
		echo "${file}: found spaces in shell script (use tabs)"
		rc=1
		((ERRORS++))
	fi

	output=$(shellcheck -f gcc -s bash -x "${file}")
	# shellcheck disable=SC2181
	if [[ $? -ne 0 ]]; then
		echo "${output}"
		rc=1
		errors=$(echo "${output}" | wc -l)
		((ERRORS+=errors))
	fi

	return ${rc}

}

lint_shell() {
	local target="${1}"
	local rc=0
	local f

	while IFS= read -r -d '' f; do
		# shellcheck disable=SC1117
		if file "${f}" | grep -qE "(shell\ script|bash\ script)"; then
			if ! _lint_shell_file "${f}"; then
				((ERROR_FILES++))
				rc=1
			fi
		fi
	done < <(find "${target}" -type f -print0)

	return ${rc}
}

lint_js() {
	local target="${1}"
	local rc=0
	local output
	local errors
	local error_files

	output=$(jshint "${target}")
	rc=$?

	if [[ ${rc} -ne 0 ]]; then
		echo "${output}" | sed -e "\$d" | sed -e "\$d"
		errors=$(echo "${output}" | tail -n1 | awk '{ print $1}')
		((ERRORS+=errors))
		error_files=$(echo "${output}" | sed -e "\$d" | sed -e "\$d" | cut -d ':' -f 1 | uniq | wc -l)
		((ERROR_FILES+=error_files))
	fi

	return ${rc}
}

lint_python() {
	# shellcheck disable=SC2124
	local targets="${@}"
	local rc=0
	local output
	local errors
	local error_files

	output=$(flake8 --max-line-length=120 --radon-max-cc="${RADON_MAX_CC}" --exclude="migrations" --count "${targets[@]}")
	rc=$?

	if [[ ${rc} -ne 0 ]]; then
		echo "${output}" | sed -e "\$d"
		errors=$(echo "${output}" | tail -n1)
		((ERRORS+=errors))
		error_files=$(echo "${output}" | sed -e "\$d" | cut -d ':' -f 1 | uniq | wc -l)
		((ERROR_FILES+=error_files))
	fi

	return ${rc}
}

check_shell() {
	local folder

	for folder in "${SH_FOLDERS[@]}"; do
		printmsg "${folder}" "checking shell scripts..."
		if lint_shell "${folder}"; then
			success "${folder}" "passed"
		else
			error "${folder}" "failed"
		fi
		echo
	done
}

check_js() {
	local folder

	for folder in ${CHECK_FOLDERS:-"${JS_FOLDERS[@]}"}; do
		printmsg "${folder}" "checking javascript files..."
		if lint_js "${folder}"; then
			success "${folder}" "passed"
		else
			error "${folder}" "failed"
		fi
		echo
	done
}

check_python() {
	local folder
	local f
	local bin_files

	if [[ -z "${CHECK_FOLDERS}" ]]; then
		for folder in "${SH_FOLDERS[@]}"; do
			printmsg "${folder}" "checking python files..."
			bin_files=()
			while IFS= read -r -d '' f; do
				if [[ "$(file "${f}")" == *"Python script"* ]]; then
					bin_files+=("${f}")
				fi
			done < <(find "${folder}" -type f -print0)
			if lint_python "${bin_files[@]}"; then
				success "${folder}" "passed"
			else
				error "${folder}" "failed"
			fi
			echo
		done

	fi

	for folder in ${CHECK_FOLDERS:-"${PY_FOLDERS[@]}"}; do
		printmsg "${folder}" "checking python files..."
		if lint_python "${folder}"; then
			success "${folder}" "passed"
		else
			error "${folder}" "failed"
		fi
		echo
	done
}

summary() {
	local rc

	echo -e "\n****************************************"
	if [[ "${ERRORS}" -eq 0 ]]; then
		rc=0
		echo -e "*** Found ${GREEN}${ERRORS}${NC} errors ${CYAN}:)${NC}"
	else
		rc=1
		echo -e "*** Found ${RED}${ERRORS}${NC} errors in ${RED}${ERROR_FILES}${NC} file(s)"
	fi
	echo -e "****************************************\n"

	return ${rc}
}


case "${CHECK_TYPE}" in
	shell|bash|sh)
		check_shell
		;;
	javascript|js)
		check_js
		;;
	python|py)
		check_python
		;;
	help|-h|--help|-?)
		echo "Usage: ${0} [all|sh|js|py] [paths]"
		exit 0
		;;
	*)
		check_shell
		check_js
		check_python
		;;
esac

summary
exit $?
