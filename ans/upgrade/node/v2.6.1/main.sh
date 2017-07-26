#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

echo "Uninstalling librabbitmq"
${ERIGONES_HOME}/bin/ctl.sh pip_uninstall