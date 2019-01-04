from django.utils.translation import ugettext_lazy as _
from api import serializers as s

DC_MODULES = (
    ('VMS_VM_REPLICATION_ENABLED', s.BooleanField(label=_('Replication'))),
)

DC_SETTINGS = (
    ('VMS_VM_REPLICA_RESERVATION_DEFAULT',
     s.BooleanField(label='VMS_VM_REPLICA_RESERVATION_DEFAULT',
                    help_text=_('Default status of VM replica\'s resource (vCPU, RAM) reservation setting. By default, '
                                'the resource reservation is enabled in order to have the vCPU and RAM available for '
                                'future failover operation.'))),
)

SETTINGS_TEMPLATES = {
    'VMS_VM_REPLICA_RESERVATION_DEFAULT': 'gui/table_form_field_checkbox.html',
}

SETTINGS_NAME = _('VM Replication')
SETTINGS_ICON = 'icon-refresh'
