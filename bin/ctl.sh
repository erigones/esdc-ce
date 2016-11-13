#!/bin/bash

if [ -f /opt/rh/python27/enable ]; then
	. /opt/rh/python27/enable
fi

MAINDIR="$(cd "$(dirname "$0")/.." ; pwd -P)"
ERIGONES_HOME=${ERIGONES_HOME:-"${MAINDIR}"}
export ERIGONES_HOME
ENVS="${ERIGONES_HOME}/envs"
PATH="${ERIGONES_HOME}/bin:/opt/local/bin:/opt/local/sbin:${ENVS}/bin:${PATH}"
export PATH
ACTIVATE="${ENVS}/bin/activate"
PYTHONPATH="${ERIGONES_HOME}:${ERIGONES_HOME}/bin:${ERIGONES_HOME}/envs/lib/python2.7/site-packages:${PYTHONPATH}"
export PYTHONPATH
MANAGEPY="${ERIGONES_HOME}/bin/manage.py"
ARGS=()
ACTION="$1"

init_envs() {
	if [ -z "${1}" ]; then
		virtualenv "${ENVS}"
	else
		virtualenv --always-copy "${ENVS}"
	fi
	activate_envs
	pip install -r "${ERIGONES_HOME}/etc/requirements-init.txt"
}

activate_envs() {
	if [ ! -f "${ACTIVATE}" ]; then
		echo "Virtual environments not found in \"${ENVS}\"!" >&2
		echo "Perhaps, you have to initialize it first with \"${0} init_envs\"." >&2
		exit 1
	fi
	source "${ACTIVATE}"
}

set_django_settings() {
	if [ -f /usr/bin/zonename ] && [ "$(/usr/bin/zonename)" == "global" ]; then
			DJANGO_SETTINGS_MODULE="core.node_settings"
	else
		case "${1}" in
			bin_*|db_dump|gendoc|git_*|*_envs|pip_*|secret_key|build|deploy)
				DJANGO_SETTINGS_MODULE="core.minimal_settings"
				;;
			*)
				DJANGO_SETTINGS_MODULE="core.settings"
				;;
		esac
	fi

	export DJANGO_SETTINGS_MODULE
}

case "${ACTION}" in
	"clean_envs")
		virtualenv --relocatable "${ENVS}"
	;;
	"init_envs")
		init_envs
	;;
	"init_envs_copy")
		init_envs "copy"
	;;
	*)
		activate_envs
		set_django_settings "$1"
		export PYTHONUNBUFFERED="true"
		"${MANAGEPY}" "${@}"
	;;
esac
