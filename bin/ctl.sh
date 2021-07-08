#!/bin/bash

MAINDIR="$(cd "$(dirname "$0")/.." || exit 64 ; pwd -P)"
ERIGONES_HOME=${ERIGONES_HOME:-"${MAINDIR}"}
export ERIGONES_HOME
ENVS="${ERIGONES_HOME}/envs"
PATH="${ERIGONES_HOME}/bin:/opt/local/bin:/opt/local/sbin:${ENVS}/bin:${PATH}"
export PATH
ACTIVATE="${ENVS}/bin/activate"
PYTHONPATH="${ERIGONES_HOME}:${ERIGONES_HOME}/bin:${ERIGONES_HOME}/envs/lib/python3.7/site-packages:${ERIGONES_HOME}/envs/lib/python3.6/site-packages:${PYTHONPATH}"
export PYTHONPATH
MANAGEPY="${ERIGONES_HOME}/bin/manage.py"
ACTION="$1"

init_envs() {
	if [ -z "${1}" ]; then
		virtualenv --python=python3.6 "${ENVS}"
	else
		virtualenv --python=python3.6 --always-copy "${ENVS}"
	fi
	activate_envs
	pip install --upgrade pip	
	pip install -r "${ERIGONES_HOME}/etc/requirements-init.txt"
}

activate_envs() {
	if [ ! -f "${ACTIVATE}" ]; then
		echo "Virtual environments not found in \"${ENVS}\"!" >&2
		echo "Perhaps, you have to initialize it first with \"${0} init_envs\"." >&2
		exit 1
	fi
	# shellcheck disable=SC1090
	source "${ACTIVATE}"
}

set_django_settings() {
	if [ -f /usr/bin/zonename ] && [ "$(/usr/bin/zonename)" == "global" ]; then
			DJANGO_SETTINGS_MODULE="core.node_settings"
	else
		case "${1}" in
			bin_*|db_dump|gendoc|git_*|*_envs|pip_*|secret_key|build|deploy|compile|esdc_*)
				DJANGO_SETTINGS_MODULE="core.minimal_settings"
				;;
			*)
				DJANGO_SETTINGS_MODULE="core.settings"
				;;
		esac
	fi

	export DJANGO_SETTINGS_MODULE
}

update_env() {
	export PYTHONUNBUFFERED="true"

	case "${1}" in
		pip_*)
			# When uninstalling or upgrading Python packages with symlinks our version of
			# Python/pip has a bug that causes the uninstall to fail in situations where
			# the default TMPDIR (/tmp) is located on a different filesystem than the virtualenv.
			# To fix this, we set TMPDIR closer to our virtualenv for all pip_* commands.
			export TMPDIR="${ERIGONES_HOME}/var"
		;;
	esac
}

exec_py() {
	local py_file="$1"
	shift

	if [[ ! -x "${py_file}" ]]; then
		echo "ERROR: File not executable: '${py_file}'"
		exit 2
	fi

	"${py_file}" "${@}"
}

case "${ACTION}" in
	"clean_envs")
		virtualenv-2.7 --relocatable "${ENVS}"
	;;
	"init_envs")
		init_envs
	;;
	"init_envs_copy")
		init_envs "copy"
	;;
	"run_raw_py")
		activate_envs
		set_django_settings default
		shift
		exec_py "${@}"
	;;
	*)
		activate_envs
		set_django_settings "$1"
		update_env "$1"
		"${MANAGEPY}" "${@}"
	;;
esac
