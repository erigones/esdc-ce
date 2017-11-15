#!/bin/bash

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
EC=0
# Settings
SH_FOLDERS=("bin")
JS_FOLDERS=("gui/static/gui/js")
# TODO: add *api* and *gui* after cleanup
PY_FOLDERS=("ans" "core" "pdns" "que" "sio" "vms")
RADON_MAX_CC="${RADON_MAX_CC:-27}"
# Colors
NC="\033[0m"
WHITE="\033[1;37m"
CYAN="\033[1;36m"
MAGENTA="\033[1;35m"
GREEN="\033[1;32m"
RED="\033[1;31m"
#######################################


printmsg() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${CYAN}${target}${NC}: ${WHITE}${msg}${NC}"
}

warning() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${CYAN}${target}${NC}: ${MAGENTA}${msg}${NC}" >&2
}

error() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${CYAN}${target}${NC}: ${RED}${msg}${NC}" >&2
}

success() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo -e "*** ${CYAN}${target}${NC}: ${GREEN}${msg}${NC}"
}

lint_shell() {
	local target="${1}"
	local rc=0

	printmsg "${target}" "checking shell script"

	if ! head -n1 "${target}" | grep -q "bash"; then
		warning "${target}" "not using bash (shebang check)"
		rc=1
	fi

	if grep -qE "^\ \ *(echo|exit|return)" "${target}"; then
		warning "${target}" "found spaces in shell script (use tabs)"
		rc=1
	fi

	if ! shellcheck -s bash -x "${target}"; then
		warning "${target}" "shellcheck failed"
		rc=1
	fi

	if [[ ${rc} -eq 0 ]]; then
		success "${target}" "passed"
	else
		error "${target}" "failed"
	fi

	return ${rc}
}

lint_js() {
	local target="${1}"
	local rc=0

	printmsg "${target}" "checking JavaScript file"

	if ! jshint "${target}"; then
		warning "${target}" "jshint failed"
		rc=1
	fi

	if [[ ${rc} -eq 0 ]]; then
		success "${target}" "passed"
	else
		error "${target}" "failed"
	fi

	return ${rc}
}

lint_python() {
	local target="${1}"
	local rc=0

	printmsg "${target}" "checking Python file"

	if ! flake8 --max-line-length=120 --radon-max-cc="${RADON_MAX_CC}" "${target}"; then
		warning "${target}" "flake8 failed"
		rc=1
	fi

	if [[ ${rc} -eq 0 ]]; then
		success "${target}" "passed"
	else
		error "${target}" "failed"
	fi

	return ${rc}
}

check_shell() {
	for folder in "${SH_FOLDERS[@]}"; do
		printmsg "Checking shell scripts in ${ERIGONES_HOME}/${folder}" "..."
		echo
		while IFS= read -r -d '' f; do
			if [[ "$(file "${f}")" == *"shell script"* ]]; then
				if ! lint_shell "${f}"; then
					EC=1
				fi
			fi
		done < <(find "${folder}" -type f -print0)
		echo
	done
}

check_js() {
	for folder in "${JS_FOLDERS[@]}"; do
		printmsg "Checking JavaScript files in ${ERIGONES_HOME}/${folder}" "..."
		echo
		while IFS= read -r -d '' f; do
			if ! lint_js "${f}"; then
				EC=1
			fi
		done < <(find "${folder}" -type f -name "*.js" -print0)
		echo
	done
}

check_python() {
	for folder in "${SH_FOLDERS[@]}"; do
		printmsg "Checking Python files in ${ERIGONES_HOME}/${folder}" "..."
		echo
		while IFS= read -r -d '' f; do
			if [[ "$(file "${f}")" == *"Python script"* ]]; then
				if ! lint_python "${f}"; then
					EC=1
				fi
			fi
		done < <(find "${folder}" -type f -print0)
		echo
	done

	for folder in "${PY_FOLDERS[@]}"; do
		printmsg "Checking Python files in ${ERIGONES_HOME}/${folder}" "..."
		echo
		while IFS= read -r -d '' f; do
			if ! lint_python "${f}"; then
				EC=1
			fi
		done < <(find "${folder}" -type f -name "*.py" -not -path "${folder}/migrations/*" -print0)
		echo
	done
}

case "${1}" in
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
		echo "Usage: ${0} [all|sh|js|py]"
		;;
	*)
		check_shell
		check_js
		check_python
		;;
esac

exit "${EC}"
