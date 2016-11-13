from django.utils.translation import ugettext_lazy as _
from django.core import validators

from api import serializers as s
from vms.models import DcNode


class DcNodeSerializer(s.InstanceSerializer):
    """
    vms.models.DcNode
    """
    _model_ = DcNode
    _update_fields_ = ('strategy', 'cpu', 'ram', 'disk', 'priority')
    _default_fields_ = ('cpu', 'ram', 'disk')

    hostname = s.Field(source='node.hostname')
    strategy = s.IntegerChoiceField(choices=DcNode.STRATEGY, default=DcNode.SHARED)
    priority = s.IntegerField(min_value=0, max_value=9999, default=100)
    cpu = s.IntegerField()
    ram = s.IntegerField()
    disk = s.IntegerField()
    cpu_free = s.IntegerField(read_only=True)
    ram_free = s.IntegerField(read_only=True)
    disk_free = s.IntegerField(read_only=True)
    ram_kvm_overhead = s.IntegerField(read_only=True)

    def __init__(self, request, instance, *args, **kwargs):
        super(DcNodeSerializer, self).__init__(request, instance, *args, **kwargs)
        if not kwargs.get('many', False):
            # Maximum = node resources
            cpu_n, ram_n, disk_n = instance.node.resources
            self.fields['cpu'].validators.append(validators.MaxValueValidator(int(cpu_n)))
            self.fields['ram'].validators.append(validators.MaxValueValidator(int(ram_n)))
            self.fields['disk'].validators.append(validators.MaxValueValidator(int(disk_n)))

            if request.method == 'PUT':
                # Minimum = used resources in this DC (recalculate from node)
                cpu_min, ram_min, disk_min = instance.node.get_used_resources(request.dc)
            else:
                # Minimum = used resources in this DC (DcNode set - DcNode free)
                cpu_min = (instance.cpu or 0) - instance.cpu_free
                ram_min = (instance.ram or 0) - instance.ram_free
                disk_min = (instance.disk or 0) - instance.disk_free

            self.fields['cpu'].validators.append(validators.MinValueValidator(cpu_min))
            self.fields['ram'].validators.append(validators.MinValueValidator(ram_min))
            self.fields['disk'].validators.append(validators.MinValueValidator(disk_min))

    def validate(self, attrs):
        strategy = int(attrs.get('strategy', self.object.strategy))

        if strategy == DcNode.RESERVED:
            cpu = int(attrs.get('cpu', self.object.cpu))
            ram = int(attrs.get('ram', self.object.ram))
            disk = int(attrs.get('disk', self.object.disk))

            cpu_nf, ram_nf, disk_nf = self.object.get_nonreserved_free_resources(exclude_this_dc=True)

            if cpu > cpu_nf:
                self._errors['cpu'] = s.ErrorList([_('Not enough free CPUs on node.')])

            if ram > ram_nf:
                self._errors['ram'] = s.ErrorList([_('Not enough free RAM on node.')])

            if disk > disk_nf:
                self._errors['disk'] = s.ErrorList([_('Not enough free disk space on node.')])

        return attrs

    def detail_dict(self, **kwargs):
        # Add dc into detail dict
        details = super(DcNodeSerializer, self).detail_dict()
        details['dc'] = self.request.dc

        return details


class ExtendedDcNodeSerializer(DcNodeSerializer):
    vms = s.IntegerField(read_only=True)
    real_vms = s.IntegerField(read_only=True)
