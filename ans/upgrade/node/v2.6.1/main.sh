#!/bin/bash

set -e

ERIGONES_HOME="${ERIGONES_HOME:-"/opt/erigones"}"
VERSION_DIR="$(cd "$(dirname "$0")" ; pwd -P)"

# https://github.com/erigones/esdc-ce/issues/207
echo "Uninstalling librabbitmq"
${ERIGONES_HOME}/bin/ctl.sh pip_uninstall --package librabbitmq