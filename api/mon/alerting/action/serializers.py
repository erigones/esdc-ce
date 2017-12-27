from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from api import serializers as s
from api.mon import MonitoringBackend
from gui.models import Role


DEFAULT_ACTION_MESSAGE_SUBJECT = "{TRIGGER.STATUS}: {TRIGGER.NAME}"

DEFAULT_ACTION_MESSAGE = """Trigger: {TRIGGER.NAME}
Trigger status: {TRIGGER.STATUS}
Trigger severity: {TRIGGER.SEVERITY}
Trigger URL: {TRIGGER.URL}

Item values:

1. {ITEM.NAME1} ({HOST.NAME1}:{ITEM.KEY1}): {ITEM.VALUE1}
2. {ITEM.NAME2} ({HOST.NAME2}:{ITEM.KEY2}): {ITEM.VALUE2}
3. {ITEM.NAME3} ({HOST.NAME3}:{ITEM.KEY3}): {ITEM.VALUE3}

Original event ID: {EVENT.ID}"""


class ActionSerializer(s.Serializer):
    name = s.SafeCharField(max_length=200)  # The name in Zabbix will be prefixed with DC name
    enabled = s.BooleanField(default=True)
    # As we implement dynamic hostgroup creation everywhere, we will not validate whether any hostgroup exists.
    # Also we don't have to have any hostgroup defined while we create the Action as it is not a required field.
    hostgroups = s.ArrayField(max_items=1024, default=[],
                              validators=(RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),))
    usergroups = s.ArrayField(max_items=1024, default=[])
    message_subject = s.CharField(max_length=255, default=DEFAULT_ACTION_MESSAGE_SUBJECT)
    message_text = s.CharField(default=DEFAULT_ACTION_MESSAGE)
    recovery_message_enabled = s.BooleanField(default=False)
    recovery_message_subject = s.CharField(max_length=255, default=DEFAULT_ACTION_MESSAGE_SUBJECT)
    recovery_message_text = s.CharField(default=DEFAULT_ACTION_MESSAGE)

    def __init__(self, request, *args, **kwargs):
        super(ActionSerializer, self).__init__(*args, **kwargs)
        self.request = request
        self.dc_settings = request.dc.settings

    def validate_usergroups(self, attrs, source):
        # User groups are created in the monitoring system according to groups in the DB. We should validate this array
        # against groups available in the current DC.
        try:
            groups_requested = set(attrs[source])
        except KeyError:
            pass
        else:
            groups_available = set(Role.objects.filter(dc=self.request.dc, name__in=groups_requested)
                                               .values_list('name', flat=True))
            groups_unavailable = groups_requested - groups_available

            if groups_unavailable:
                raise s.ValidationError([_('User group with name=%s does not exist.') % group
                                         for group in groups_unavailable])

        return attrs
