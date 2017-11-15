#!/bin/bash

#######################################
MAINDIR="$(cd "$(dirname "$0")/.." || exit 128 ; pwd -P)"
ERIGONES_HOME=${ERIGONES_HOME:-"${MAINDIR}"}
export ERIGONES_HOME
cd "${ERIGONES_HOME}" || exit 64
#######################################
EC=0
#######################################


error() {
	local target="${1}"
	shift
	local msg="${*:-""}"

	echo "${target} :: ${msg}" >&2
}

lint_shell() {
	local target="${1}"
	local rc=0

	echo "*** Checking shell script ${target} ***"

	if ! head -n1 "${target}" | grep -q "bash"; then
		error "${target}" "Not using bash (shebang check)"
		rc=1
	fi

	if grep -qE "^\ \ *(echo|exit|return)" "${target}"; then
		error "${target}" "Found spaces in shell script (use tabs)"
		rc=1
	fi

	if ! shellcheck -s bash -x "${target}"; then
		rc=1
	fi

	return ${rc}
}

while IFS= read -r -d '' f; do
	if [[ "$(file "${f}")" == *"shell script"* ]]; then
		if ! lint_shell "${f}"; then
			EC=1
		fi
	fi
done < <(find bin -type f -print0)

exit "${EC}"
