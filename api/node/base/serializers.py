from frozendict import frozendict

from api import serializers as s
from vms.models import Node


class NodeSerializer(s.Serializer):
    """
    Node details serializer (read-only).
    """
    hostname = s.Field()
    address = s.Field()
    status = s.IntegerChoiceField(choices=Node.STATUS_DB, read_only=True)
    node_status = s.DisplayChoiceField(source='status', choices=Node.STATUS_DB, read_only=True)
    owner = s.SlugRelatedField(slug_field='username', read_only=True)
    is_head = s.BooleanField(read_only=True)
    cpu = s.IntegerField(source='cpu_total', read_only=True)
    ram = s.IntegerField(source='ram_total', read_only=True)
    cpu_free = s.IntegerField(read_only=True)
    ram_free = s.IntegerField(read_only=True)
    ram_kvm_overhead = s.IntegerField(read_only=True)


class ExtendedNodeSerializer(NodeSerializer):
    """
    Extended node details serializer (read-only).
    """
    extra_select = frozendict({
        'vms': '''SELECT COUNT(*) FROM "vms_vm" WHERE "vms_node"."uuid" = "vms_vm"."node_id"''',
        'real_vms': '''SELECT COUNT(*) FROM "vms_vm" LEFT OUTER JOIN "vms_slavevm" ON
    ( "vms_vm"."uuid" = "vms_slavevm"."vm_id" ) WHERE "vms_node"."uuid" = "vms_vm"."node_id" AND
    "vms_slavevm"."id" IS NULL''',
        'snapshots': '''SELECT COUNT(*) FROM "vms_snapshot" LEFT OUTER JOIN "vms_vm" ON
    ( "vms_vm"."uuid" = "vms_snapshot"."vm_id" ) WHERE "vms_node"."uuid" = "vms_vm"."node_id"''',
        'backups': '''SELECT COUNT(*) FROM "vms_backup" WHERE "vms_node"."uuid" = "vms_backup"."node_id"'''
    })

    dcs = s.DcsField()
    vms = s.IntegerField(read_only=True)
    snapshots = s.IntegerField(read_only=True)
    backups = s.IntegerField(read_only=True)
    real_vms = s.IntegerField(read_only=True)
