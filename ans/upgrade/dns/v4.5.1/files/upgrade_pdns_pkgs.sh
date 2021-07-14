#!/bin/sh

set -x
set -e

# "pkgin upgrade" will not downgrade packages so it is future-safe even on re-exec

#/opt/local/bin/pkgin -y install powerdns-4.2.2 powerdns-pgsql-4.2.2 powerdns-recursor-4.3.1 dnsdist-1.3.3nb1
/opt/local/bin/pkgin -y upgrade powerdns-4.4.0 powerdns-pgsql-4.4.0 powerdns-recursor-4.4.2 dnsdist-1.5.1
set +e

/opt/local/bin/timeout 100 /usr/sbin/svcadm disable -st pdns pdns-recursor pdns-dnsdist

# recursor tends to hang after upgrade
if pkill -0 pdns_recursor; then
        pkill -9 pdns_recursor
fi

for svc in pdns pdns-recursor pdns-dnsdist; do
	/opt/pdns-confd/contrib/smartos-reload-smf.sh restart "${svc}"
done
