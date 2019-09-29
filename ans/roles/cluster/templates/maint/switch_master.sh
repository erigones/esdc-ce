#!/bin/sh

# Usage:
# - without parameters: move master away from this node
# - with parameter: cluster member name - move master there

# Output: nothing
# Exit status:
# - zero: switch succeeded
# - non-zero: it did not go smoothly, check cluster status


if [ $(whoami) != "root" ]; then
        echo "Please run this script as user root!"
        exit 1
fi

CLUSTER_RES_NAME="{{ cluster_postgres_HA_res_name }}"
TO_HOST="$1"

if ! crm_node -l &> /dev/null; then
        # cluster is not running!
        exit 1
fi

if [[ -z "${TO_HOST}" ]]; then
	# if hostname not specified, evacuate this node
	/usr/sbin/pcs resource ban "$CLUSTER_RES_NAME" "$(crm_node -n)" --master lifetime=PT1M &> /dev/null
	(( rc = rc + $? ))
else
	# switch master to specified node
	if crm_node -l | grep -q " ${TO_HOST} "; then
		/usr/sbin/pcs resource move "$CLUSTER_RES_NAME" "${TO_HOST}" --master lifetime=PT1M
		(( rc = rc + $? ))
	else
		echo "Host name ${TO_HOST} was not found in the cluster. Aborting."
		exit 5
	fi
fi

# clear resource
sleep 30
/usr/sbin/pcs resource clear "$CLUSTER_RES_NAME"
(( rc = rc + $? ))

exit "${rc}"
