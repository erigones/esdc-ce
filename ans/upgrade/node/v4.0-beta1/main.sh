#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

echo "+ Updating 020-ipsec-restore.sh"
cp -f "${VERSION_DIR}/files/020-ipsec-restore.sh" "/opt/custom/etc/rc-pre-network.d/020-ipsec-restore.sh"

