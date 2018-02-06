#!/bin/sh

ndd -set ip ipsec_policy_log_interval 1
ikeadm set debug all
cat << EOF

IPSec debugging enabled. See these logfiles:
/var/log/in.iked.log (for phase 1 and 2)
/var/adm/messages    (for packet drops)

EOF
