#!/bin/bash

set -e

# ensure ansible is installed
if ! [ -x /usr/bin/ansible-playbook ]; then
	echo "Installing ansible package"
	yum -y -q install ansible
fi

MAINDIR="$(cd "$(dirname "$0")/.." ; pwd -P)"
ERIGONES_HOME=${ERIGONES_HOME:-"${MAINDIR}"}
ANS_BASE="${ERIGONES_HOME}/ans"
UPG_BASE="${ERIGONES_HOME}/ans/upgrade"
export ERIGONES_HOME UPG_BASE

PYTHONPATH="$ERIGONES_HOME:$PYTHONPATH:$ERIGONES_HOME/envs/lib/python2.7/site-packages"
VIRTUAL_ENV="$ERIGONES_HOME/envs"
export PYTHONPATH VIRTUAL_ENV

# Update ansible inventory
${ERIGONES_HOME}/bin/ctl.sh genhosts > "${ANS_BASE}/hosts.cfg"

# pre-v2.3.1 check
if [[ ! -f "/root/.ssh/id_rsa" ]]; then
	echo "Generating SSH key pair for this server"
	ssh-keygen -t rsa -b 2048 -f /root/.ssh/id_rsa -q -P ""
	cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
	echo
	echo "*********  !!! WARNING !!!  **********"
	echo "Please copy manually public key /root/.ssh/id_rsa.pub from this server"
	echo "to other servers (mon01, img01, dns01, etc) and press any key to continue."
	echo "*********  !!! WARNING !!!  **********"
	read
fi

# upgrade only instances of the same number (so we can perform rolling upgrades if there are more of them)
MYHOSTNAME=$(hostname -s)				# e.g: mgmt01
APPLIANCE_NUMBER="${MYHOSTNAME:(-2)}"	# e.g: "01"

cd "${ANS_BASE}"
/usr/bin/ansible-playbook "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="runhosts='mgmt${APPLIANCE_NUMBER}' appliance_type=mgmt"
/usr/bin/ansible-playbook "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="runhosts='mon${APPLIANCE_NUMBER}' appliance_type=mon"

