from django.core.validators import RegexValidator

from api import serializers as s
from api.mon import MonitoringBackend


DEFAULT_ACTION_MESSAGE_SUBJECT = "{TRIGGER.STATUS}: {TRIGGER.NAME}"

DEFAULT_ACTION_MESSAGE = """Trigger: {TRIGGER.NAME}
Trigger status: {TRIGGER.STATUS}
Trigger severity: {TRIGGER.SEVERITY}
Trigger URL: {TRIGGER.URL}

Item values:

1. {ITEM.NAME1} ({HOST.NAME1}:{ITEM.KEY1}): {ITEM.VALUE1}
2. {ITEM.NAME2} ({HOST.NAME2}:{ITEM.KEY2}): {ITEM.VALUE2}
3. {ITEM.NAME3} ({HOST.NAME3}:{ITEM.KEY3}): {ITEM.VALUE3}

Original event ID: {EVENT.ID}
"""


class ActionSerializer(s.Serializer):
    hostgroups = s.ArrayField(max_items=16384, default=[], validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),),
                              )

    usergroups = s.ArrayField(max_items=16384, default=[], validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),),
                              )

    message_subject = s.SafeCharField(max_length=65536, default=DEFAULT_ACTION_MESSAGE_SUBJECT)  # TODO initial value zo zabbixu vykopirovat a dat do settings
    message_text = s.SafeCharField(max_length=65536, default=DEFAULT_ACTION_MESSAGE)  # TODO initial value zo zabbixu vykopirovat a dat do settings
    recovery_message_enabled = s.BooleanField(default=False, required=False)
    recovery_message_text = s.SafeCharField(max_length=65536, required=False)  # TODO initial value zo zabbixu vykopirovat, conditional validation

    def validate_hostgroups(self, attrs, source):
        # Allow to use only available hostgroups
        return attrs
        raise NotImplementedError
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.object.monitoring_hostgroups == value:
                return attrs
            elif self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_RESTRICT and not \
                    set(value).issubset(set(self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_ALLOWED)):
                raise s.ValidationError(_('Selected monitoring hostgroups are not available.'))

        return attrs

    def validate_usergroups(self, attrs, source):
        # Allow to use only available hostgroups
        return attrs

        raise NotImplementedError
        try:
            value = attrs[source]
        except KeyError:
            pass
        else:
            if self.object and self.object.monitoring_hostgroups == value:
                return attrs
            elif self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_RESTRICT and not \
                    set(value).issubset(set(self.dc_settings.MON_ZABBIX_HOSTGROUPS_VM_ALLOWED)):
                raise s.ValidationError(_('Selected monitoring hostgroups are not available.'))

        return attrs