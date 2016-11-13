"""
NOTE: Signals are great and we are using them to start subsequent processes.
(e.g. create monitoring host after VM is defined)
However, extra caution is required. Example: An _atomic_ view can create a VM, which is actually saved in the DB after
the view is done. But during the view, a signal is called, which loads the VM from DB. The signal function may not find
the VM in the DB because the parent view is still running...
"""
from blinker import signal


# (task_id, vm=vm, old_state=old_state, new_state=state)
vm_status_changed = signal('vm_status_changed', doc='VM status on node changed.')
# (task_id, vm_uuid=uuid, zoneid=zoneid, old_zoneid=zoneid_cache)
vm_zoneid_changed = signal('vm_zoneid_changed', doc='VM zone ID on node changed.')
# (task_id, vm=vm, old_state=old_state)
vm_running = signal('vm_running', doc='VM changed status to RUNNING.')
# (task_id, vm=vm, old_state=old_state)
vm_stopped = signal('vm_stopped', doc='VM changed status to STOPPED.')
# (task_id, vm=vm)
vm_defined = signal('vm_defined', doc='VM defined in DB with NOTCREATED status')
# (task_id, vm_uuid=uuid, vm_hostname=hostname, vm_alias=alias, dc=request.dc, zabbix_sync=zabbix_sync,
#  external_zabbix_sync=external_zabbix_sync)
vm_undefined = signal('vm_undefined', doc='VM removed from DB')
# (task_id, vm=vm)
vm_created = signal('vm_created', doc='VM changed status from CREATING to DEPLOYING.')
# (task_id, vm=vm)
vm_deployed = signal('vm_deployed', doc='VM changed status from DEPLOYING to RUNNING or STOPPED.')
# (task_id, vm=vm)
vm_notcreated = signal('vm_notcreated', doc='VM changed status to NOTCREATED.')
# (task_id, vm=vm)
vm_node_changed = signal('vm_node_changed', doc='VM node changed (probably after migration).')
# (task_id, vm=vm)
vm_json_active_changed = signal('vm_json_active_changed', doc='VM json and json_active were updated, which means '
                                                              'that DB json is now synchronized with node json.')
# (task_id, vm=vm)
vm_updated = signal('vm_updated', doc='VM has been updated, but only locally (node update was not run)')

# (task_id, node=node, automatic=(bool))
node_status_changed = signal('node_status_changed', doc='Node status was changed.')
# (task_id, node=node, automatic=(bool))
node_online = signal('node_online', doc='Node changed status to ONLINE')
# (task_id, node=node)
node_offline = signal('node_offline', doc='Node changed status to OFFLINE')
# (task_id, node=node)
node_unreachable = signal('node_unreachable', doc='Node changed status to UNREACHABLE')
# (task_id, node=node)
node_unlicensed = signal('node_unlicensed', doc='Node changed status to UNLICENSED')
# (task_id, node=node
node_created = signal('node_created', doc='Node was created.')
# (task_id, node_uuid=uuid, node_hostname=hostname)
node_deleted = signal('node_deleted', doc='Node was deleted.')
# (task_id, node=node)
node_json_changed = signal('node_json_changed', doc='Node json was updated.')
# (sender, node=node)
node_check = signal('node_check', doc='Node check called every minute by node_status_all()')

# (task_id, dc=dc, old_settings={}, new_settings={})
dc_settings_changed = signal('dc_settings_changed', doc='DC settings were changed.')
