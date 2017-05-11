from vms.signals import (vm_defined, vm_undefined, vm_updated, node_status_changed, node_online, node_offline,
                         node_unlicensed, node_unreachable, node_deleted, dc_settings_changed)
from api.node.sshkey.tasks import node_authorized_keys_sync
from api.node.handlers import dc_node_settings_changed_handler
from api.node.sysinfo.handlers import node_startup
from api.node.status.events import node_status_changed_event
from api.vm.status.tasks import vm_status_all
from api.mon.vm.tasks import mon_vm_sync, mon_vm_delete
from api.mon.node.tasks import mon_node_status_sync, mon_node_delete
from api.imagestore.base.handlers import imagestore_settings_changed_handler
from api.mon.base.tasks import mon_user_group_changed, mon_user_changed
from blinker import signal

# noinspection PyUnusedLocal
def noop(*args, **kwargs):
    return None


vm_defined.connect(noop)
vm_undefined.connect(mon_vm_delete.call)
vm_updated.connect(mon_vm_sync.call)
node_status_changed.connect(mon_node_status_sync.call)
node_status_changed.connect(node_status_changed_event)
node_online.connect(node_authorized_keys_sync.call)
node_online.connect(node_startup)
node_online.connect(vm_status_all)
node_offline.connect(noop)
node_unlicensed.connect(noop)
node_unreachable.connect(noop)
node_deleted.connect(mon_node_delete.call)
dc_settings_changed.connect(dc_node_settings_changed_handler)
dc_settings_changed.connect(imagestore_settings_changed_handler)

# todo presunut niekam kde to ma byt, api.accounts alebo gui.models
dc_access_changed = signal('dc_access_changed', doc='Datacenter access group changed.')
group_changed = signal('group_changed', doc='Access group changed.')
user_changed = signal('user_changed', doc='User details changed.')

dc_access_changed.connect(mon_user_group_changed.call) #FIXME
group_changed.connect(mon_user_group_changed.call) #FIXME
user_changed.connect(mon_user_changed.call) #FIXME

# Note: Other signals are connected in api.mon.vm.tasks and api.mon.node.tasks
