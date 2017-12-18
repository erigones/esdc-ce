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
    # TODO change to as in user groups in user creation
    name = s.SafeCharField(max_length=65536, required=True)

    hostgroups = s.ArrayField(max_items=16384, default=[], validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),),
                              )

    usergroups = s.ArrayField(max_items=16384, default=[], validators=(
                                             RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),),
                              )

    message_subject = s.SafeCharField(max_length=65536, default=DEFAULT_ACTION_MESSAGE_SUBJECT)
    message_text = s.SafeCharField(max_length=65536, default=DEFAULT_ACTION_MESSAGE)
    # TODO recovery message boolean to turn on/off
    recovery_message_text = s.SafeCharField(max_length=65536, required=False)
    # TODO add also status enabled/disabled

    def validate_hostgroups(self, attrs, source):
        # As we implmement everywhere dynamic hostgroup creation, we will not validate whether any hostgroup exist.
        # Also we don't have to have any hostgroup defined while we create the Action as it is not a required field.
        from api.mon.backends.zabbix.base import ZabbixHostGroupContainer

        attrs[source] = [ZabbixHostGroupContainer.hostgroup_name_factory(name, self.context.dc.name) for name in attrs[source]]
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
        # TODO take the usergroup validation from api/dc/base/serializers

        from api.mon.backends.zabbix.base import ZabbixUserGroupContainer

        attrs[source] = [ZabbixUserGroupContainer.user_group_name_factory(self.context.dc.name, name)
                         for name in attrs[source]]
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


class ActionUpdateSerializer(s.Serializer):
    hostgroups = s.ArrayField(max_items=16384, validators=(
        RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),), required=False)

    usergroups = s.ArrayField(max_items=16384, validators=(
        RegexValidator(regex=MonitoringBackend.RE_MONITORING_HOSTGROUPS),), required=False)

    message_subject = s.SafeCharField(max_length=65536, required=False)

    message_text = s.SafeCharField(max_length=65536, required=False)

    recovery_message_text = s.SafeCharField(max_length=65536, required=False)

    def validate_hostgroups(self, attrs, source):
        # As we implmement everywhere dynamic hostgroup creation, we will not validate whether any hostgroup exist.
        # Also we don't have to have any hostgroup defined while we create the Action as it is not a required field.
        from api.mon.backends.zabbix.base import ZabbixHostGroupContainer
        if source in attrs:
            attrs[source] = [ZabbixHostGroupContainer.hostgroup_name_factory(name, self.context.dc.name)
                             for name in attrs[source]]
        return attrs

    def validate_usergroups(self, attrs, source):
        # TODO take the usergroup validation from api/dc/base/serializers

        from api.mon.backends.zabbix.base import ZabbixUserGroupContainer
        if source in attrs:
            attrs[source] = [ZabbixUserGroupContainer.user_group_name_factory(self.context.dc.name, name)
                             for name in attrs[source]]
        return attrs
