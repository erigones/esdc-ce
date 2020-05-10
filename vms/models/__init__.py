from __future__ import absolute_import
from django.db.models.signals import post_delete, post_save

from vms.models.dc import Dc, DummyDc, DefaultDc, DomainDc  # noqa: F401
from vms.models.storage import Storage, NodeStorage  # noqa: F401
from vms.models.iso import Iso  # noqa: F401
from vms.models.vmtemplate import VmTemplate  # noqa: F401
from vms.models.image import Image, ImageVm  # noqa: F401
from vms.models.imagestore import ImageStore  # noqa: F401
from vms.models.node import Node, DcNode  # noqa: F401
from vms.models.vm import TagVm, Vm  # noqa: F401
from vms.models.slave_vm import SlaveVm  # noqa: F401
from vms.models.snapshot import SnapshotDefine, Snapshot  # noqa: F401
from vms.models.subnet import Subnet  # noqa: F401
from vms.models.ipaddress import IPAddress  # noqa: F401
from vms.models.tasklog import TaskLogEntry  # noqa: F401
from vms.models.backup import BackupDefine, Backup  # noqa: F401
from pdns.models import Domain  # noqa: F401

TASK_MODELS = (Image, Vm, Node, NodeStorage, Dc)  # The order here is important!
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

post_save.connect(Subnet.post_save_subnet, sender=Subnet, dispatch_uid='post_save_subnet')
post_delete.connect(Subnet.post_delete_subnet, sender=Subnet, dispatch_uid='post_delete_subnet')
