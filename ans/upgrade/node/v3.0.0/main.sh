#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

#
# https://github.com/erigones/esdc-factory/commit/6861ab0b
#
echo "+ Updating /opt/zabbix/etc/scripts/kvmiostat"
cat "${VERSION_DIR}/files/kvmiostat" > "/opt/zabbix/etc/scripts/kvmiostat"
svcadm restart svc:/application/zabbix/vm-kvm-disk-io-monitor

#
# https://github.com/erigones/esdc-factory/issues/89
#
CUSTOM_ETC="/opt/custom/etc"
SRC_CUSTOM_ETC="${VERSION_DIR}/files/custom-etc"

mkdir -p "${CUSTOM_ETC}"

for srcdir in "${SRC_CUSTOM_ETC}"/*; do
	dirname="$(basename "${srcdir}")"
	if [[ ! -e "${CUSTOM_ETC}/${dirname}" ]]; then
		echo "+ Placing ${dirname} into ${CUSTOM_ETC}"
		cp -a "${srcdir}" "${CUSTOM_ETC}"
	fi
done

#
# https://github.com/erigones/esdc-factory/issues/102
#
OPENSSL="/opt/local/bin/openssl"
OPENSSL_CERTS="/opt/local/etc/openssl/certs"
SVC_CERT_FILE_NAME="dc-erigonesd.pem"
SVC_CERT_FILE_TMP="/tmp/${SVC_CERT_FILE_NAME}.$$"
SVC_CERT_FILE="${CUSTOM_ETC}/${SVC_CERT_FILE_NAME}"  # Uses CUSTOM_ETC set above
CTLSH="${ERIGONES_HOME}/bin/ctl.sh"
ERIGONESD_CONFIG="${ERIGONES_HOME}/core/celery/local_config.py"
ERIGONESD_CONFIG_BKP="${ERIGONESD_CONFIG}.$$.bkp"

if [[ -f "${SVC_CERT_FILE}" ]] && "${ERIGONES_HOME}/bin/query_cfgdb" get /esdc/settings/dc/datacenter_name > /dev/null; then
	echo "+ SSL certificate for internal services is already configured"
else
	# Fetch SSL certificate from cfgdb and save it to a temporary location
	if ! "${ERIGONES_HOME}/bin/query_cfgdb" --legacy get /esdc/settings/security/services_ssl_cert > "${SVC_CERT_FILE_TMP}"; then
		echo "ERROR: SSL certificate for internal services not found" 1>&2
		exit 31
	fi

	# Check SSL certificate
	if ! grep -q "\-END CERTIFICATE\-" "${SVC_CERT_FILE_TMP}"; then
		echo "ERROR: Invalid SSL certificate for internal services" 1>&2
		exit 32
	fi

	# Install SSL certificate to a predetermined location
	echo "+ Installing SSL certificate for Danube Cloud services"
	mv "${SVC_CERT_FILE_TMP}" "${SVC_CERT_FILE}"

	# Make the esdc SSL certificate available for other clients
	(
	cd ${OPENSSL_CERTS}
	ln -s "${SVC_CERT_FILE}" "${SVC_CERT_FILE_NAME}" || true
	ln -s "${SVC_CERT_FILE_NAME}" "$("${OPENSSL}" x509 -hash -noout -in "${SVC_CERT_FILE}").0" || true
	)

	# Test SSL connection to ZK REST
	if ! "${ERIGONES_HOME}/bin/query_cfgdb" get /esdc/settings/dc/datacenter_name > /dev/null; then
		echo "ERROR: SSL connection to cfgdb has failed"
		exit 33
	fi
fi

if grep -q "^BROKER_USE_SSL" "${ERIGONESD_CONFIG}"; then
	echo "+ erigonesd is already configured to connect via SSL"
	exit 0
fi

# For the next operation we need to patch celery in our virtualenv
echo "+ Installing the patch program"
pkgin -y install patch > /dev/null

echo "+ Patching packages in virtualenv"
"${CTLSH}" patch_envs > /dev/null

# Create backup of erigonesd configuration (local_config.py)
cp -a "${ERIGONESD_CONFIG}" "${ERIGONESD_CONFIG_BKP}"

# Something has failed -> restore backup (trap to ERR does not work)
trap '[[ "$?" -ne 0 ]] && mv "${ERIGONESD_CONFIG_BKP}" "${ERIGONESD_CONFIG}"' EXIT

# Configure SSL connection to rabbitmq and redis
echo "+ Configuring erigonesd to connect via SSL"
sed -i '' -e 's|:5672/|:15672/|' -e 's|:6379/|:16379/|' "${ERIGONESD_CONFIG}"
cat >> "${ERIGONESD_CONFIG}" << EOF

import ssl

BROKER_USE_SSL = { 'cert_reqs': ssl.CERT_REQUIRED, 'ca_certs': '${SVC_CERT_FILE}' }
REDIS_BACKEND_USE_SSL = { 'ssl_cert_reqs': ssl.CERT_REQUIRED, 'ssl_ca_certs': '${SVC_CERT_FILE}' }
EOF

# Test SSL connection to RabbitMQ and Redis
if "${CTLSH}" service_check --node; then
	rm -f "${ERIGONESD_CONFIG_BKP}"  # we good -> remove backup
else
	echo "ERROR: SSL connection to mgmt has failed"
	exit 34
fi
