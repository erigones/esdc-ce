#!/bin/bash

set -e

VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

echo "+ Updating /opt/zabbix/etc/scripts/kstat"
cat "${VERSION_DIR}/files/kstat" > "/opt/zabbix/etc/scripts/kstat"
