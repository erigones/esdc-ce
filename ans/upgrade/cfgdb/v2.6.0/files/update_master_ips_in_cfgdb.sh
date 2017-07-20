
for vm in mgmt mon cfgdb dns img; do
	CURR_VAL="$(query_cfgdb get "/esdc/vms/esdc-${vm}/master/id" 2>/dev/null)"
	if [[ -z "${CURR_VAL}" ]]; then
		query_cfgdb creater "/esdc/vms/esdc-${vm}/master/id" "1"
	fi

	VM_IP="$(query_cfgdb get "/esdc/vms/esdc-${vm}/hosts/1/ip")"
	CURR_VAL="$(query_cfgdb get "/esdc/vms/esdc-${vm}/master/ip" 2>/dev/null)"
	if [[ -z "${CURR_VAL}" ]]; then
		query_cfgdb creater "/esdc/vms/esdc-${vm}/master/ip" "${VM_IP}"
	else
		query_cfgdb set "/esdc/vms/esdc-${vm}/master/ip" "${VM_IP}"
	fi
done

