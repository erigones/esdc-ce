#!/bin/sh -e

# ensure ansible is installed
if ! [ -x /usr/bin/ansible-playbook ]; then
	echo "Installing ansible package"
	yum -y -q install ansible
fi

ERIGONES_HOME=${ERIGONES_HOME:="/opt/erigones"}
UPG_BASE="${ERIGONES_HOME}/ans/upgrade"
INVENTORY="${ERIGONES_HOME}/ans/hosts"
ANSIBLE_CFG="${ERIGONES_HOME}/ans/ansiblecfg"
export ERIGONES_HOME UPG_BASE

# load ansible config
if [ -f "$ANSIBLE_CFG" ]; then
	. "$ANSIBLE_CFG"
fi

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

/usr/bin/ansible-playbook -i "${INVENTORY}" "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="runhosts='mgmt${APPLIANCE_NUMBER}' appliance_type=mgmt"
#/usr/bin/ansible-playbook -i "${INVENTORY}" "${UPG_BASE}/lib/runupgrade.yml" --extra-vars="runhosts='mon${APPLIANCE_NUMBER}' appliance_type=mon"

