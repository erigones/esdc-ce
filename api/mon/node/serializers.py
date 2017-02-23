from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.mon.serializers import MonHistorySerializer


class DiskMonNodeHistorySerializer(MonHistorySerializer):
    """
    Used by NodeHistoryView to validate zpools value.
    """
    zpool = s.CharField(required=True)

    def validate(self, attrs):
        zpool = attrs.get('zpool')
        assert zpool

        if zpool in self.obj.zpools:
            self.item_id = zpool
        else:
            raise s.ValidationError(_('Zpool ID not defined on the node.'))

        return attrs


class NetworkMonNodeHistorySerializer(MonHistorySerializer):
    """
    Used by NodeHistoryView to validate nic_id value.
    """
    nic = s.CharField(required=True)

    def validate(self, attrs):
        nic = attrs.get('nic')
        assert nic

        if nic in self.obj.used_nics:
            self.item_id = nic
        else:
            raise s.ValidationError(_('NIC ID not defined on the node.'))

        return attrs
