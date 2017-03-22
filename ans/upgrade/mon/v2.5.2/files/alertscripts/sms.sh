#!/bin/bash

PHONE="${1}" # Set this in user media
shift
# Everything else is the message itself
MSG=$(echo "${@}" | sed 's/|\?\*UNKNOWN\*|\?//g')

/etc/zabbix/alertscripts/hqsms.py "${PHONE}" "${MSG}"
