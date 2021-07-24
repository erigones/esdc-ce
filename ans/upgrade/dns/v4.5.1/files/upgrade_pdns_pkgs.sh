#!/usr/bin/env bash

set -e

declare -A PKGS
PKGS[powerdns]=4.4.0
PKGS[powerdns-pgsql]=4.4.0
PKGS[powerdns-recursor]=4.4.2
PKGS[dnsdist]=1.5.1

SERVICES="pdns pdns-recursor pdns-dnsdist"

### START ###

DC_REPO="$(cat /opt/local/etc/pkgin/repositories.conf | grep -i danube)"

if [ "$(wc -l <<< "${DC_REPO}")" -ne 1 ]; then
	echo "ERROR: Danube repo was not found in pkgin repo list"
	exit 10
fi

PKG_LIST="$(pkg_info)"
for pkg in "${!PKGS[@]}"; do
	if ! grep "^${pkg}-[0-9]" <<< "${PKG_LIST}"; then
		echo "Warning: package '${pkg}' is not installed"
	fi
done

set -x

cd /tmp
for pkg in "${!PKGS[@]}"; do
	pkg_fullname="${pkg}-${PKGS[$pkg]}"
	/opt/local/bin/curl -sO "${DC_REPO}/${pkg_fullname}"
done

# stop services before upgrade
/opt/local/bin/timeout 100 /usr/sbin/svcadm disable -st ${SERVICES}

set +e	# uninstall can fail
# remove pkgs
for pkg in "${!PKGS[@]}"; do
	/opt/local/sbin/pkg_delete "${pkg}"
done
set -e

# install new pkgs
for pkg in "${!PKGS[@]}"; do
	pkg_fullname="${pkg}-${PKGS[$pkg]}"
	/opt/local/sbin/pkg_add "${pkg_fullname}"
	rm "${pkg_fullname}"
done


# start services back
for svc in ${SERVICES}; do
	/opt/pdns-confd/contrib/smartos-reload-smf.sh restart "${svc}"
done

### END ###
