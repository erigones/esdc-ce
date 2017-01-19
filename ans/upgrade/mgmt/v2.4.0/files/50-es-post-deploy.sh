#!/bin/bash

PATH="/usr/pgsql-9.5/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
DONE_FILE="/var/lib/es-post-deploy.done"
SCRIPT="${0}"
ERIGONES_HOME="/opt/erigones"
SETTINGS="${ERIGONES_HOME}/core/local_settings.py"
CELERY_CONFIG="${ERIGONES_HOME}/core/celery/local_config.py"
CTL="${ERIGONES_HOME}/bin/ctl.sh"

log() {
	logger -t "${SCRIPT}" "$@"
}

esdc_pre_boot() {
	cd ${ERIGONES_HOME}

	git checkout var/run/.gitignore
	git checkout var/tmp/.gitignore
	git checkout var/www/static/.gitignore

	log "Running ${CTL} pre_boot"
	log "$(sudo -u erigones ${CTL} pre_boot 2>&1)"

	# Warm-up tomcat/guacamole hack
	(
	  curl -s http://127.0.0.1:8080/guacamole/ > /dev/null
	  curl -s -X POST -d '{"username": "test", "password": "test"}' http://127.0.0.1:8080/guacamole/api/tokens > /dev/null
	) &
}

if [[ -f "${DONE_FILE}" ]]; then
	log "Found ${DONE_FILE} - skipping post-deploy configuration"
	sleep 60        # give time to all services to initialize
	esdc_pre_boot
	exit 0
fi

log "Starting post-deploy configuration"

AUTHORIZED_KEYS="$(mdata-get root_authorized_keys || echo '')"
log "Populating authorized_keys"
mkdir -pm 700 /root/.ssh
echo "${AUTHORIZED_KEYS}" > /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
sleep 3

log "Generating SSL certificate"
openssl req -new -nodes -x509 \
-subj "/C=SK/ST=Slovakia/L=Bratislava/O=IT/CN=*.*" \
-days 3650 \
-keyout /etc/pki/tls/certs/server.key \
-out /etc/pki/tls/certs/server.crt \
-extensions v3_ca

cat /etc/pki/tls/certs/server.key /etc/pki/tls/certs/server.crt > /etc/pki/tls/certs/server.pem
chown root:root /etc/pki/tls/certs/server.pem
chmod 600 /etc/pki/tls/certs/server.pem
chmod 600 /etc/pki/tls/certs/server.key

log "Restaring haproxy"
systemctl restart haproxy

# RabbitMQ
RABBITMQ_HOST="127.0.0.1"
RABBITMQ_PORT="5672"
RABBITMQ_VHOST="esdc"
RABBITMQ_USERNAME="esdc"
RABBITMQ_PASSWORD="$(mdata-get org.erigones:rabbitmq_password 2> /dev/null)"
log "Metadata key org.erigones:rabbitmq_password value=${RABBITMQ_PASSWORD}"
if [[ -n "${RABBITMQ_PASSWORD}" ]]; then
	log "Changing RabbitMQ password for user ${RABBITMQ_USERNAME}"
	rabbitmqctl change_password "${RABBITMQ_USERNAME}" "${RABBITMQ_PASSWORD}"
else
	RABBITMQ_PASSWORD="S3cr3tP4ssw0rd"
fi

# Redis
REDIS_HOST="127.0.0.1"
REDIS_PORT="6379"
REDIS_PASSWORD="$(mdata-get org.erigones:redis_password 2> /dev/null)"
log "Metadata key org.erigones:redis_password value=${REDIS_PASSWORD}"
if [[ -n "${REDIS_PASSWORD}" ]]; then
	log "Changing redis password"
	sed -i "s/^requirepass.*/requirepass ${REDIS_PASSWORD}/" /etc/redis.conf
	log "Restarting redis"
	systemctl restart redis
else
	REDIS_PASSWORD="S3cr3tP4ssw0rd"
fi

# Guacamole
if [[ -n "${REDIS_PASSWORD}" ]]; then
	log "Changing redis password for guacamole"
	sed -i "s/^redis-password:.*/redis-password: ${REDIS_PASSWORD}/" /var/lib/tomcat/webapps/guacamole/WEB-INF/classes/guacamole.properties
	log "Restarting tomcat"
	systemctl restart tomcat
fi


# PostgreSQL
PGSQL_ESDC_HOST="127.0.0.1"
PGSQL_ESDC_PORT="6432"
PGSQL_ESDC_USERNAME="esdc"
PGSQL_ESDC_PASSWORD="$(mdata-get org.erigones:pgsql_esdc_password 2> /dev/null)"
PGSQL_PDNS_USERNAME="pdns"
PGSQL_PDNS_PASSWORD="$(mdata-get org.erigones:pgsql_pdns_password 2> /dev/null)"
PGSQL_MON_USERNAME="stats"
PGSQL_MON_PASSWORD="$(openssl rand -base64 30 | tr -dc _A-Z-a-z-0-9)"
log "Metadata key org.erigones:pgsql_esdc_password value=${PGSQL_ESDC_PASSWORD}"
log "Metadata key org.erigones:pgsql_pdns_password value=${PGSQL_PDNS_PASSWORD}"
if [[ -n "${PGSQL_ESDC_PASSWORD}" ]]; then
	log "Changing PostgreSQL password for user ${PGSQL_ESDC_USERNAME}"
	if psql -tA -U postgres -c "ALTER USER ${PGSQL_ESDC_USERNAME} WITH PASSWORD '${PGSQL_ESDC_PASSWORD}';" postgres; then
		esdc_passwd=$(psql -tA -U postgres -c "SELECT passwd from pg_shadow WHERE usename='${PGSQL_ESDC_USERNAME}'" postgres)
		sed -i "s/^\"${PGSQL_ESDC_USERNAME}\".*/\"${PGSQL_ESDC_USERNAME}\" \"${esdc_passwd}\"/" /etc/pgbouncer/userlist.txt
	fi
else
	PGSQL_ESDC_PASSWORD="S3cr3tP4ssw0rd"
fi
if [[ -n "${PGSQL_PDNS_PASSWORD}" ]]; then
	log "Changing PostgreSQL password for user ${PGSQL_PDNS_USERNAME}"
	if psql -tA -U postgres -c "ALTER USER ${PGSQL_PDNS_USERNAME} WITH PASSWORD '${PGSQL_PDNS_PASSWORD}';" postgres; then
		pdns_passwd=$(psql -tA -U postgres -c "SELECT passwd from pg_shadow WHERE usename='${PGSQL_PDNS_USERNAME}'" postgres)
		sed -i "s/^\"${PGSQL_PDNS_USERNAME}\".*/\"${PGSQL_PDNS_USERNAME}\" \"${pdns_passwd}\"/" /etc/pgbouncer/userlist.txt
	fi
fi
if [[ -n "${PGSQL_MON_PASSWORD}" ]]; then
	log "Changing PostgreSQL password for user ${PGSQL_MON_USERNAME}"
	if psql -tA -U postgres -c "ALTER USER ${PGSQL_MON_USERNAME} WITH PASSWORD '${PGSQL_MON_PASSWORD}';" postgres; then
		mon_passwd=$(psql -tA -U postgres -c "SELECT passwd from pg_shadow WHERE usename='${PGSQL_MON_USERNAME}'" postgres)
		sed -i "s/^\"${PGSQL_MON_USERNAME}\".*/\"${PGSQL_MON_USERNAME}\" \"${mon_passwd}\"/" /etc/pgbouncer/userlist.txt
		sed -i "s/:${PGSQL_MON_USERNAME}:.*/:${PGSQL_MON_USERNAME}:${PGSQL_MON_PASSWORD}/" /var/lib/zabbix/.pgpass
	fi
fi
log "Restarting pdbouncer"
systemctl restart pgbouncer

# Zabbix Agent
ZABBIX_AGENT_CONFIG="/etc/zabbix/zabbix_agentd.conf"
ZABBIX_IP="$(mdata-get org.erigones:zabbix_ip 2>/dev/null || echo '127.0.0.1')"
log "Metadata key org.erigones:zabbix_ip value=${ZABBIX_IP}"
sed -i "s/^Server=.*/Server=${ZABBIX_IP}/" "${ZABBIX_AGENT_CONFIG}"
sed -i "s/^ServerActive=.*/ServerActive=${ZABBIX_IP}/" "${ZABBIX_AGENT_CONFIG}"
sed -i "s/@REDIS_PASSWORD@/${REDIS_PASSWORD}/g" "${ZABBIX_AGENT_CONFIG}"
log "Restarting zabbix-agent"
systemctl restart zabbix-agent

# esDC
log "Updating esDC celery/local_config.py"
sed -i -e "s/@RABBITMQ_PASSWORD@/${RABBITMQ_PASSWORD}/g" \
	   -e "s/@REDIS_PASSWORD@/${REDIS_PASSWORD}/g" "${CELERY_CONFIG}"

log "Generating Django secret key"
SECRET_KEY="$(openssl rand -base64 42)"
sed -i '/^SECRET_KEY\s\+=/d' "${SETTINGS}"
echo "SECRET_KEY=\"\"\"${SECRET_KEY}\"\"\"" >> "${SETTINGS}"

log "Updating esDC local_settings.py"
sed -i -e "s/@PGSQL_ESDC_PASSWORD@/${PGSQL_ESDC_PASSWORD}/g" \
	   -e "s/@REDIS_PASSWORD@/${REDIS_PASSWORD}/g" "${SETTINGS}"

ZABBIX_SERVER="$(mdata-get org.erigones:zabbix_server 2> /dev/null || echo "${ZABBIX_IP}")"
log "Metadata key org.erigones:zabbix_server value=${ZABBIX_SERVER}"
[[ -n "${ZABBIX_SERVER}" ]] && \
	echo "MON_ZABBIX_SERVER = 'https://${ZABBIX_SERVER}/'" >> "${SETTINGS}"

ZABBIX_ESDC_USERNAME="$(mdata-get org.erigones:zabbix_esdc_username 2> /dev/null)"
log "Metadata key org.erigones:zabbix_esdc_username value=${ZABBIX_ESDC_USERNAME}"
[[ -n "${ZABBIX_ESDC_USERNAME}" ]] && \
	echo "MON_ZABBIX_USERNAME = '${ZABBIX_ESDC_USERNAME}'" >> "${SETTINGS}"

ZABBIX_ESDC_PASSWORD="$(mdata-get org.erigones:zabbix_esdc_password 2> /dev/null)"
log "Metadata key org.erigones:zabbix_esdc_password value=${ZABBIX_ESDC_PASSWORD}"
[[ -n "${ZABBIX_ESDC_PASSWORD}" ]] && \
	echo "MON_ZABBIX_PASSWORD = '${ZABBIX_ESDC_PASSWORD}'" >> "${SETTINGS}"

# esDC services
log "Enabling/starting esDC services"
for svc in "erigonesd" "erigonesd-beat" "esdc@gunicorn-sio" "esdc@gunicorn-api" "esdc@gunicorn-gui"; do
	systemctl enable "${svc}"
	systemctl start "${svc}"
done

# esDC configuration
ESDC_ADMIN_EMAIL="$(mdata-get org.erigones:esdc_admin_email 2> /dev/null)"
log "Metadata key org.erigones:esdc_admin_email value=${ESDC_ADMIN_EMAIL}"
if [[ -n "${ESDC_ADMIN_EMAIL}" ]]; then
	sleep 5
	${ERIGONES_HOME}/bin/es login -username admin -password changeme
	${ERIGONES_HOME}/bin/es set /accounts/user/admin -email "${ESDC_ADMIN_EMAIL}"
	${ERIGONES_HOME}/bin/es logout
fi

# esDC
esdc_pre_boot

touch "${DONE_FILE}"
log "Finished post-deploy configuration"
exit 0
