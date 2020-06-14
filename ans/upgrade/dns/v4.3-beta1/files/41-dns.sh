#!/bin/bash

MDATA_PREFIX="org.erigones"
PDNS_CONFIG="/opt/local/etc/pdns.conf"
PDNS_RECURSOR_CONFIG="/opt/local/etc/recursor.conf"
PDNS_CONFD_CONFIG="/opt/local/etc/pdns-confd.ini"

declare -A PDNS_MDATA=(
	[pgsql_host]="gpgsql-host"
	[pgsql_port]="gpgsql-port"
	[pgsql_user]="gpgsql-user"
	[pgsql_password]="gpgsql-password"
	[pgsql_dbname]="gpgsql-dbname"
)

declare -A PDNS_RECURSOR_MDATA=(
	[recursor_forwarders]="forward-zones-recurse"
)

declare -A PDNS_CONFD_MDATA=(
	[pgsql_host]="@PGSQL_HOST@"
	[pgsql_port]="@PGSQL_PORT@"
	[pgsql_user]="@PGSQL_USER@"
	[pgsql_password]="@PGSQL_PASSWORD@"
	[pgsql_dbname]="@PGSQL_DBNAME@"
)

update_config() {
	local mdata_key="${1}"
	local config_var="${2}"
	local config_file="${3}"
	local comment_char="${4:-#}"
	local mdata_value
	local config_value

	log "reading metadata key: \"${mdata_key}\""
	mdata_value=$(mdata-get "${mdata_key}" 2>/dev/null)

	# shellcheck disable=SC2181
	if [[ $? -eq 0 ]]; then
		log "found metadata key: \"${mdata_key}\" value: \"${mdata_value}\""
		if [[ -z "${mdata_value}" ]]; then
			log "empty metadata value for key \"${mdata_key}\" -> commenting out \"${config_var}\"!"
			config_value="${comment_char}${config_var}="
		else
			config_value="${config_var}=${mdata_value}"
		fi
		if gsed -i "/^${config_var}=/s/${config_var}.*/${config_value}/" "${config_file}"; then
			log "set ${config_var}=${mdata_value} in ${config_file}"
		else
			log "failed to set ${config_var}=${mdata_value} in ${config_file}"
		fi
	else
		log "missing metadata key: \"${mdata_key}\" (ignoring ${config_var} in ${config_file})"
	fi
}

replace_string_by_mdata() {
	local mdata_key="${1}"
	local old_string="${2}"
	local config_file="${3}"
	local mdata_value

	log "reading metadata key: \"${mdata_key}\""
	mdata_value=$(mdata-get "${mdata_key}" 2>/dev/null)

	if gsed -i "s/${old_string}/${mdata_value}/g" "${config_file}"; then
		log "set ${old_string} => ${mdata_value} in ${config_file}"
	else
		log "failed to set ${old_string} => ${mdata_value} in ${config_file}"
	fi
}

log "reading pdns metadata and configuring ${PDNS_CONFIG}"
for key in "${!PDNS_MDATA[@]}"; do
	update_config "${MDATA_PREFIX}:${key}" "${PDNS_MDATA[$key]}" "${PDNS_CONFIG}"
done

log "reading pdns metadata and configuring ${PDNS_RECURSOR_CONFIG}"
for key in "${!PDNS_RECURSOR_MDATA[@]}"; do
	update_config "${MDATA_PREFIX}:${key}" "${PDNS_RECURSOR_MDATA[$key]}" "${PDNS_RECURSOR_CONFIG}"
done

log "reading pdns metadata and configuring ${PDNS_CONFD_MDATA}"
for key in "${!PDNS_CONFD_MDATA[@]}"; do
	replace_string_by_mdata "${MDATA_PREFIX}:${key}" "${PDNS_CONFD_MDATA[$key]}" "${PDNS_CONFD_CONFIG}"
done

log "starting PowerDNS services"
svcadm enable -s pdns
svcadm enable -s pdns-recursor
svcadm enable -s pdns-dnsdist
svcadm enable -s pdns-confd
