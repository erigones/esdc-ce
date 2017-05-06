#!/bin/bash
#
# Danube Cloud VM post-deploy configuration
#

PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
DONE_FILE="/var/lib/es-post-deploy.done"
SCRIPT="${0}"

log() {
	logger -t "${SCRIPT}" "$@"
}

zbx() {
	out=$(echo "${2}" | es-zabbix-config.py "${1}" 2>&1)
	e=$?
	log "${out}"

	if [[ "${e}" -eq 0 ]]; then
		log "Zabbix API command ${1} was successful"
	else
		log "Error running Zabbix API command ${1}"
	fi

	return "${e}"
}

log "Populating authorized_keys"
AUTHORIZED_KEYS="$(mdata-get root_authorized_keys || echo '')"
mkdir -pm 700 /root/.ssh
while read -r AUTHKEY; do
	[ -z "$AUTHKEY" ] && continue
	if ! grep -q "^$AUTHKEY$" /root/.ssh/authorized_keys 2> /dev/null; then
		echo "$AUTHKEY" >> /root/.ssh/authorized_keys
	fi
done <<< "$AUTHORIZED_KEYS"
chmod 600 /root/.ssh/authorized_keys

# check if post-deploy was already processed
if [[ -f "${DONE_FILE}" ]]; then
	log "Found ${DONE_FILE} - skipping post-deploy configuration"
	exit 0
fi

log "Starting post-deploy configuration"

log "Generating SSL certificate"
openssl req -new -nodes -x509 \
-subj "/C=SK/ST=Slovakia/L=Bratislava/O=IT/CN=*.*" \
-days 3650 \
-keyout /etc/pki/tls/certs/server.key \
-out /etc/pki/tls/certs/server.crt \
-extensions v3_ca

chmod 600 /etc/pki/tls/certs/server.key

log "Restarting httpd"
systemctl restart httpd

ZABBIX_AGENT_CONFIG="/etc/zabbix/zabbix_agentd.conf"
ZABBIX_IP="$(mdata-get org.erigones:zabbix_ip 2>/dev/null || echo '127.0.0.1')"
log "Metadata key org.erigones:zabbix_ip value=${ZABBIX_IP}"
sed -i "s/^Server=.*/Server=${ZABBIX_IP}/" "${ZABBIX_AGENT_CONFIG}"
sed -i "s/^ServerActive=.*/ServerActive=${ZABBIX_IP}/" "${ZABBIX_AGENT_CONFIG}"
systemctl restart zabbix-agent

ZABBIX_ADMIN_EMAIL="$(mdata-get org.erigones:zabbix_admin_email 2> /dev/null)"
log "Metadata key org.erigones:zabbix_admin_email value=${ZABBIX_ADMIN_EMAIL}"
[[ -n "${ZABBIX_ADMIN_EMAIL}" ]] && \
	zbx user.addmedia "{\"users\": [{\"userid\": 1}], \"medias\": {\"mediatypeid\": \"1\", \"sendto\": \"${ZABBIX_ADMIN_EMAIL}\", \"active\": 0, \"severity\": 63, \"period\": \"1-7,00:00-24:00\"}}"

ZABBIX_SMTP_EMAIL="$(mdata-get org.erigones:zabbix_smtp_email 2> /dev/null)"
log "Metadata key org.erigones:zabbix_smtp_email value=${ZABBIX_SMTP_EMAIL}"
[[ -n "${ZABBIX_SMTP_EMAIL}" ]] && \
	zbx mediatype.update "{\"mediatypeid\": \"1\", \"smtp_email\": \"${ZABBIX_SMTP_EMAIL}\"}"

ZABBIX_ESDC_PASSWORD="$(mdata-get org.erigones:zabbix_esdc_password 2> /dev/null)"
log "Metadata key org.erigones:zabbix_esdc_password value=${ZABBIX_ESDC_PASSWORD}"
[[ -n "${ZABBIX_ESDC_PASSWORD}" ]] && \
	zbx user.update "{\"userid\": 3, \"passwd\": \"${ZABBIX_ESDC_PASSWORD}\"}"

# Must be last because this password is used in previous API calls
ZABBIX_ADMIN_PASSWORD="$(mdata-get org.erigones:zabbix_admin_password 2> /dev/null)"
log "Metadata key org.erigones:zabbix_admin_password value=${ZABBIX_ADMIN_PASSWORD}"
[[ -n "${ZABBIX_ADMIN_PASSWORD}" ]] && \
	zbx user.update "{\"userid\": 1, \"passwd\": \"${ZABBIX_ADMIN_PASSWORD}\"}"

touch "${DONE_FILE}"
log "Finished post-deploy configuration"
exit 0
