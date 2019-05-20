from logging import getLogger

from django.db import IntegrityError, transaction
from django.core.validators import RegexValidator
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from api import serializers as s
from api.mon import MonitoringBackend
from api.validators import validate_owner
from api.vm.utils import get_owners
from api.node.status.utils import node_ping
from vms.models import Node
from gui.models import User

logger = getLogger(__name__)


class NodeDefineSerializer(s.InstanceSerializer):
    """
    vms.models.Node
    """
    error_negative_resources = s.ErrorList([_('Value is too low because of existing virtual machines.')])

    _model_ = Node
    _update_fields_ = ('status', 'owner', 'address', 'is_compute', 'is_backup', 'note', 'cpu_coef', 'ram_coef',
                       'monitoring_hostgroups', 'monitoring_templates')

    hostname = s.CharField(read_only=True)
    uuid = s.CharField(read_only=True)
    address = s.ChoiceField()
    status = s.IntegerChoiceField(choices=Node.STATUS_DB)
    node_status = s.DisplayChoiceField(source='status', choices=Node.STATUS_DB, read_only=True)
    owner = s.SlugRelatedField(slug_field='username', queryset=User.objects, read_only=False)
    is_head = s.BooleanField(read_only=True)
    is_compute = s.BooleanField()
    is_backup = s.BooleanField()
    note = s.CharField(required=False)
    cpu = s.IntegerField(source='cpu_total', read_only=True)
    ram = s.IntegerField(source='ram_total', read_only=True)
    cpu_coef = s.DecimalField(min_value=0, max_digits=4, decimal_places=2)
    ram_coef = s.DecimalField(min_value=0, max_value=5, max_digits=4, decimal_places=2)
    cpu_free = s.IntegerField(read_only=True)
    ram_free = s.IntegerField(read_only=True)
    ram_kvm_overhead = s.IntegerField(read_only=True)
    sysinfo = s.Field(source='api_sysinfo')  # Field is read_only=True by default
    monitoring_hostgroups = s.ArrayField(max_items=16, default=[],
                                         validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),))
    monitoring_templates = s.ArrayField(max_items=32, default=[])
    created = s.DateTimeField(read_only=True, required=False)

    def __init__(self, request, instance, *args, **kwargs):
        super(NodeDefineSerializer, self).__init__(request, instance, *args, **kwargs)
        self.clear_cache = False
        self.status_changed = False
        self.address_changed = False
        self.old_ip_address = None
        self.monitoring_changed = False

        if not kwargs.get('many', False):
            # Valid node IP addresses
            self.fields['address'].choices = [(ip, ip) for ip in instance.ips]
            # Used for update_node_resources()
            self._cpu_coef = instance.cpu_coef
            self._ram_coef = instance.ram_coef
            # Only active users
            self.fields['owner'].queryset = get_owners(request)

    def validate_owner(self, attrs, source):
        """Cannot change owner while pending tasks exist"""
        validate_owner(self.object, attrs.get(source, None), _('Compute node'))

        return attrs

    def validate_address(self, attrs, source):
        """Mark that node IP address is going to change"""
        new_address = attrs.get(source, None)

        if new_address and self.object.address != new_address:
            self.address_changed = True

            try:
                self.old_ip_address = self.object.ip_address
            except ObjectDoesNotExist:
                self.old_ip_address = None

        return attrs

    def validate_status(self, attrs, source):
        """Mark the status change -> used for triggering the signal.
        Do not allow a manual status change from unlicensed status."""
        try:
            value = attrs[source]
        except KeyError:
            return attrs

        if self.object.status != value:
            node = self.object

            if node.is_unlicensed():
                raise s.ValidationError(_('Cannot change status. Please add a valid license first.'))

            if node.is_unreachable() or node.is_offline():          # Manual switch from unreachable and offline state
                if settings.DEBUG:
                    logger.warning('DEBUG mode on => skipping status checking of node %s', self.object)
                elif not node_ping(self.object, all_workers=False):   # requires that node is really online
                    raise s.ValidationError(_('Cannot change status. Compute node is down.'))

            self.clear_cache = True
            self.status_changed = value

        return attrs

    def validate_is_compute(self, attrs, source):
        """Search for defined VMs when turning compute capability off"""
        if source in attrs and self.object.is_compute != attrs[source]:
            if self.object.vm_set.exists():
                raise s.ValidationError(_('Found existing VMs on node.'))
            self.clear_cache = True

        return attrs

    def validate_is_backup(self, attrs, source):
        """Search for existing backup definitions, which are using this node"""
        if source in attrs and self.object.is_backup != attrs[source]:
            if self.object.backupdefine_set.exists():
                raise s.ValidationError(_('Found existing VM backup definitions.'))
            self.clear_cache = True

        # Check existing backups when removing node
        if self.request.method == 'DELETE':
            if self.object.backup_set.exists():
                raise s.ValidationError(_('Found existing VM backups.'))
            self.clear_cache = True

        return attrs

    def validate_monitoring_hostgroups(self, attrs, source):
        """Mark the monitoring change -> used for triggering the signal"""
        if source in attrs and self.object.monitoring_hostgroups != attrs[source]:
            self.monitoring_changed = True

        return attrs

    def validate_monitoring_templates(self, attrs, source):
        """Mark the monitoring change -> used for triggering the signal"""
        if source in attrs and self.object.monitoring_templates != attrs[source]:
            self.monitoring_changed = True

        return attrs

    @property
    def update_node_resources(self):
        """True if cpu_coef or ram_coef changed"""
        return not(self.object.cpu_coef == self._cpu_coef and self.object.ram_coef == self._ram_coef)

    def save(self):
        """Update compute node attributes in database"""
        node = self.object

        # NOTE:
        # Changing cpu or disk coefficients can lead to negative numbers in node.cpu/ram_free or dc_node.cpu/ram_free
        try:
            with transaction.atomic():
                node.save(update_resources=self.update_node_resources, clear_cache=self.clear_cache)

                if self.update_node_resources:
                    if node.cpu_free < 0 or node.dcnode_set.filter(cpu_free__lt=0).exists():
                        raise IntegrityError('cpu_check')

                    if node.ram_free < 0 or node.dcnode_set.filter(ram_free__lt=0).exists():
                        raise IntegrityError('ram_check')

        except IntegrityError as exc:
            errors = {}
            exc_error = str(exc)
            # ram or cpu constraint was violated on vms_dcnode (can happen when DcNode strategy is set to RESERVED)
            # OR a an exception was raised above
            if 'ram_check' in exc_error:
                errors['ram_coef'] = self.error_negative_resources
            if 'cpu_check' in exc_error:
                errors['cpu_coef'] = self.error_negative_resources

            if not errors:
                raise exc

            return errors

        if self.update_node_resources:  # cpu_free or ram_free changed
            self.reload()

        return None
