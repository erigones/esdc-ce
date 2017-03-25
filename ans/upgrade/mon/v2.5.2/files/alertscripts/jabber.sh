#!/bin/sh

JID=${1}
shift
MSG=$(echo "${@}" | sed 's/|\?\*UNKNOWN\*|\?//g')

curl -s -m 3 -o /dev/null -d "jid=${JID}&msg=${MSG}" http://127.0.0.1:8922/alert
