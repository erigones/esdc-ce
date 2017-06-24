
for vm in mgmt mon cfgdb dns img; do
    query_cfgdb creater /esdc/vms/esdc-${vm}/master/id "1"
    VM_IP="$(query_cfgdb get /esdc/vms/esdc-${vm}/hosts/1/ip)"
    query_cfgdb creater /esdc/vms/esdc-${vm}/master/ip "${VM_IP}"
done

