from api import serializers as s
from api.vm.base.serializers import VmSerializer as _VmSerializer, ExtendedVmSerializer as _ExtendedVmSerializer


class VmSerializer(_VmSerializer):
    dc = s.Field(source='dc.name')


class ExtendedVmSerializer(_ExtendedVmSerializer):
    dc = s.Field(source='dc.name')
