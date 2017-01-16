#!/bin/sh

# ensure ansible is installed
if ! [ -x /usr/bin/ansible-playbook ]; then
	echo "Installing ansible package"
	yum -y -q install ansible
fi

ERIGONES_HOME=${ERIGONES_HOME:="/opt/erigones"}
UPG_BASE="${ERIGONES_HOME}/ans/upgrade"
export ERIGONES_HOME UPG_BASE

# upgrade only instances of the same number (so we can perform rolling upgrades if there are more)
MYHOSTNAME=$(hostname -s)				# e.g: mgmt01
APPLIANCE_NUMBER="${MYHOSTNAME:(-2)}"	# e.g: "01"

/usr/bin/ansible-playbook "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="hosts='mgmt${APPLIANCE_NUMBER}' appliance=mgmt"
#/usr/bin/ansible-playbook "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="hosts='mon${APPLIANCE_NUMBER}' appliance=mon"

