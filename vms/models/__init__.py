from __future__ import absolute_import
from django.db.models.signals import post_delete

from vms.models.dc import Dc, DummyDc, DefaultDc, DomainDc
from vms.models.storage import Storage, NodeStorage
from vms.models.iso import Iso
from vms.models.vmtemplate import VmTemplate
from vms.models.image import Image, ImageVm
from vms.models.imagestore import ImageStore
from vms.models.node import Node, DcNode
from vms.models.vm import TagVm, Vm
from vms.models.slave_vm import SlaveVm
from vms.models.snapshot import SnapshotDefine, Snapshot
from vms.models.subnet import Subnet
from vms.models.ipaddress import IPAddress
from vms.models.tasklog import TaskLogEntry
from vms.models.backup import BackupDefine, Backup
from pdns.models import Domain

TASK_MODEL_KEYS = ('dc_id', 'image_uuid', 'vm_uuid', 'node_uuid', 'nodestorage_id')  # The order here is important!
STATUS_MODELS = (Node, Vm, Snapshot, Backup)
SCHEDULE_MODELS = (SnapshotDefine, BackupDefine)

for i in STATUS_MODELS:
    post_delete.connect(i.post_delete_status, sender=i, dispatch_uid='post_delete_status_' + i.__name__)

for i in SCHEDULE_MODELS:
    post_delete.connect(i.post_delete_schedule, sender=i, dispatch_uid='pre_delete_schedule_' + i.__name__)

post_delete.connect(Vm.post_delete, sender=Vm, dispatch_uid='post_delete_vm')
post_delete.connect(SlaveVm.post_delete, sender=SlaveVm, dispatch_uid='post_delete_slave_vm')
post_delete.connect(DcNode.post_delete, sender=DcNode, dispatch_uid='post_delete_dc_node')
post_delete.connect(NodeStorage.post_delete, sender=NodeStorage, dispatch_uid='post_delete_ns')
post_delete.connect(DomainDc.domain_post_delete, sender=Domain, dispatch_uid='post_delete_domain')
