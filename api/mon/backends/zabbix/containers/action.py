from django.utils.six import text_type, iteritems
from frozendict import frozendict

from api.mon.backends.zabbix.exceptions import (RemoteObjectDoesNotExist, RelatedRemoteObjectDoesNotExist,
                                                RemoteObjectManipulationError)
from api.mon.backends.zabbix.containers.base import ZabbixBaseContainer
from api.mon.backends.zabbix.containers.host_group import ZabbixHostGroupContainer
from api.mon.backends.zabbix.containers.user_group import ZabbixUserGroupContainer

trans_name = ZabbixBaseContainer.trans_dc_qualified_name
trans_noop = ZabbixBaseContainer.trans_noop
trans_bool = ZabbixBaseContainer.trans_bool
trans_bool_inverted = ZabbixBaseContainer.trans_bool_inverted


class ZabbixActionContainer(ZabbixBaseContainer):
    """
    Container for the Zabbix Action object
    Initially it should contain only necessary elements for successful creation of a Zabbix Action object,
    but it should be easily extensible to accommodate all the customization possibilities of the Zabbix Action.

    Should have:
    - checking of all the fields undefined by us but changed (should warn and discard action)
      also in the operations
    - conditiontypes should be checked whether they are implemented at our side (if not then discard action)
    - support only evaltype And/Or, discard the others but make them implementable
    - operation steps and durations - do some reasonable defaults and discard action if changed
    - editable: hostgroups, usergroups, optional recovery message, default message,
    """
    ZABBIX_ID_ATTR = 'actionid'
    NAME_MAX_LENGTH = 255
    # TODO; optimize query
    QUERY_BASE = frozendict({'output': 'extend', 'selectOperations': 'extend', 'selectFilter': 'extend'})

    _BASE_PARAMS_MAPPING = (
        ('name', 'name', trans_name),
        ('status', 'enabled', trans_bool_inverted),
        ('def_shortdata', 'message_subject', trans_noop),
        ('def_longdata', 'message_text', trans_noop),
        ('recovery_msg', 'recovery_message_enabled', trans_bool),
        ('r_shortdata', 'recovery_message_subject', trans_noop),
        ('r_longdata', 'recovery_message_text', trans_noop),
    )

    _BASE_PARAMS_DEFAULTS = frozendict({
        'eventsource': 0,   # 0 = trigger  (we will not support other event sources)
        'esc_period': 300,  # we have only one operation and do not support escalations
    })

    _EVALTYPE_DEFAULT = 0  # we support only "AND / OR"

    _FILTER_PARAMS_DEFAULTS = frozendict({
        'evaltype': _EVALTYPE_DEFAULT,

    })

    _CONDITION_TRIGGER_PROBLEM = frozendict({
        'conditiontype': 5,
        'operator': 0,
        'value': '1',
    })

    _CONDITION_STATUS_NOT_IN_MAINTENANCE = frozendict({
        'conditiontype': 16,
        'operator': 7,
        'value': '',
    })

    _CONDITION_HOST_GROUP_DEFAULTS = frozendict({
        'conditiontype': 0,
        'operator': 0,
        'value': NotImplemented,
    })

    _MESSAGE_OPERATION_PARAMS_DEFAULTS = frozendict({
        'operationtype': 0,
        'opmessage': {
            'mediatypeid': 0,
            'default_msg': 1,
        },
        'opmessage_grp': NotImplemented,
        'opconditions': [
            {'conditiontype': 14, 'operator': 0, 'value': '0'}  # Event is not acknowledged
        ]
    })

    usergroups = None  # type: [ZabbixUserGroupContainer]
    hostgroups = None  # type: [ZabbixHostGroupContainer]

    def init(self, zabbix_object, validate=True, resolve_hostgroups=True, resolve_usergroups=True):
        super(ZabbixActionContainer, self).init(zabbix_object)

        if validate and not self._is_supported(zabbix_object):
            raise RemoteObjectManipulationError('Monitoring action \"%s\" has unsupported configuration'
                                                % self.name_without_dc_prefix)

        if resolve_hostgroups:
            self.refresh_hostgroups()

        if resolve_usergroups:
            self.refresh_usergroups()

    @classmethod
    def user_group_name_factory(cls, dc_name, action_name):
        """
        We have to qualify the dc name to prevent name clashing among actions in different datacenters,
        but in the same zabbix.
        """
        name = cls.trans_dc_qualified_name(action_name, dc_name)

        if len(name) > cls.NAME_MAX_LENGTH:
            raise ValueError('dc_name + action name should have less than %d chars, but they have %d instead: %s %s'
                             % (cls.NAME_MAX_LENGTH-3, len(name), dc_name, action_name))

        return name

    @classmethod
    def from_zabbix_data(cls, zapi, zabbix_object, **init_kwargs):
        return cls(zabbix_object['name'], zapi=zapi, zabbix_object=zabbix_object, **init_kwargs)

    @classmethod
    def from_mgmt_data(cls, zapi, name):
        return cls(name, zapi=zapi)

    @classmethod
    def from_zabbix_name(cls, zapi, name, **init_kwargs):
        container = cls(name, zapi=zapi)
        container.refresh(**init_kwargs)

        return container

    @classmethod
    def _is_supported(cls, zabbix_object):
        operations = zabbix_object.get('operations', [])
        action_filter = zabbix_object.get('filter', {})
        conditions = action_filter.get('conditions', [])

        # Check operations
        check_operations = (
            not operations or
            (len(operations) == 1 and
             'opmessage_grp' in operations[0] and
             int(operations[0]['operationtype']) == cls._MESSAGE_OPERATION_PARAMS_DEFAULTS['operationtype'])
        )

        # Check filter base setup
        check_filter = (
            text_type(action_filter.get(key)) == text_type(val)
            for key, val in iteritems(cls._FILTER_PARAMS_DEFAULTS)
        )

        # Check filter conditions
        check_conditions = (
            (int(condition.get('conditiontype')) == cls._CONDITION_HOST_GROUP_DEFAULTS['conditiontype'] and
             int(condition.get('operator')) == cls._CONDITION_HOST_GROUP_DEFAULTS['operator'])
            or
            (int(condition.get('conditiontype')) == cls._CONDITION_TRIGGER_PROBLEM['conditiontype'] and
             int(condition.get('operator')) == cls._CONDITION_TRIGGER_PROBLEM['operator'] and
             text_type(condition.get('value')) == text_type(cls._CONDITION_TRIGGER_PROBLEM['value']))
            or
            (int(condition.get('conditiontype')) == cls._CONDITION_STATUS_NOT_IN_MAINTENANCE['conditiontype'] and
             int(condition.get('operator')) == cls._CONDITION_STATUS_NOT_IN_MAINTENANCE['operator'] and
             text_type(condition.get('value')) == text_type(cls._CONDITION_STATUS_NOT_IN_MAINTENANCE['value']))
            for condition in conditions
        )

        return check_operations and all(check_filter) and all(check_conditions)

    @classmethod
    def _is_visible_from_dc(cls, zabbix_object, dc_name):
        match = cls.RE_NAME_WITH_DC_PREFIX.match(zabbix_object['name'])

        return match and dc_name == match.group('dc_name')

    @classmethod
    def all(cls, zapi, dc_name):
        response = cls.call_zapi(zapi, 'action.get', params=dict(cls.QUERY_BASE))
        # Actions with invalid names or unsupported/manually-modified parameters are not shown in list view
        response = (action for action in response
                    if cls._is_visible_from_dc(action, dc_name) and cls._is_supported(action))

        return [cls.from_zabbix_data(zapi, item, validate=False) for item in response]

    def _prepare_hostgroups(self, dc_name, mgmt_hostgroups):
        for mgmt_name in mgmt_hostgroups:
            name = ZabbixHostGroupContainer.hostgroup_name_factory(dc_name, mgmt_name)

            yield ZabbixHostGroupContainer.get_or_create(self._zapi, name)

    def _prepare_usergroups(self, dc_name, mgmt_usergroups):
        for mgmt_name in mgmt_usergroups:
            name = ZabbixUserGroupContainer.user_group_name_factory(dc_name, mgmt_name)

            try:
                usergroup = ZabbixUserGroupContainer.from_zabbix_name(self._zapi, name, resolve_users=False)
            except RemoteObjectDoesNotExist:
                raise RelatedRemoteObjectDoesNotExist('User Group \"%s\" does not exist in the monitoring '
                                                      'system' % mgmt_name)

            yield usergroup

    @classmethod
    def _generate_hostgroup_condition(cls, hostgroup_id):
        condition = dict(cls._CONDITION_HOST_GROUP_DEFAULTS)
        condition['value'] = hostgroup_id

        return condition

    def _generate_conditions(self):
        conditions = [dict(self._CONDITION_TRIGGER_PROBLEM), dict(self._CONDITION_STATUS_NOT_IN_MAINTENANCE)]
        conditions.extend(self._generate_hostgroup_condition(hostgroup.zabbix_id) for hostgroup in self.hostgroups)

        return conditions

    def _generate_operations(self):
        if self.usergroups:
            operation = dict(self._MESSAGE_OPERATION_PARAMS_DEFAULTS)
            operation['opmessage_grp'] = [{u'usrgrpid': usergroup.zabbix_id} for usergroup in self.usergroups]

            return [operation]
        else:
            return []

    def _generate_create_params(self, dc_name, create_mgmt_data):
        params = dict(self._BASE_PARAMS_DEFAULTS)

        # Action base attributes
        for zbx_key, mgmt_key, transform_fun in self._BASE_PARAMS_MAPPING:
            params[zbx_key] = transform_fun(create_mgmt_data[mgmt_key], from_zabbix=False, dc_name=dc_name)

        # Filter conditions
        self.hostgroups = list(self._prepare_hostgroups(dc_name, create_mgmt_data['hostgroups']))
        params['filter'] = dict(self._FILTER_PARAMS_DEFAULTS)
        params['filter']['conditions'] = self._generate_conditions()

        # Operations
        self.usergroups = list(self._prepare_usergroups(dc_name, create_mgmt_data['usergroups']))
        params['operations'] = self._generate_operations()

        return params

    def _generate_update_params(self, dc_name, update_mgmt_data):
        assert self.zabbix_id, 'Cannot update Action without actionid'
        # For some reason the status must be there for action.update
        params = {'actionid': self.zabbix_id, 'status': int(self.zabbix_object['status'])}

        # Action base attributes
        for zbx_key, mgmt_key, transform_fun in self._BASE_PARAMS_MAPPING:
            if mgmt_key in update_mgmt_data:
                params[zbx_key] = transform_fun(update_mgmt_data[mgmt_key], from_zabbix=False, dc_name=dc_name)

        # Filter conditions
        if 'hostgroups' in update_mgmt_data:
            self.hostgroups = list(self._prepare_hostgroups(dc_name, update_mgmt_data['hostgroups']))
            params['filter'] = dict(self._FILTER_PARAMS_DEFAULTS)
            params['filter']['conditions'] = self._generate_conditions()

        # Operations
        if 'usergroups' in update_mgmt_data:
            self.usergroups = list(self._prepare_usergroups(dc_name, update_mgmt_data['usergroups']))
            params['operations'] = self._generate_operations()

        return params

    def refresh_hostgroups(self):
        conditions = self.zabbix_object.get('filter', {}).get('conditions', [])
        hostgroup_ids = set(int(cond['value']) for cond in conditions
                            if int(cond['conditiontype']) == self._CONDITION_HOST_GROUP_DEFAULTS['conditiontype'])

        self.hostgroups = ZabbixHostGroupContainer.from_zabbix_ids(self._zapi, list(hostgroup_ids))

    def refresh_usergroups(self):
        operations = self.zabbix_object.get('operations', [])
        opmessage_groups = (op['opmessage_grp'] for op in operations
                            if ('opmessage_grp' in op and
                                int(op['operationtype']) == self._MESSAGE_OPERATION_PARAMS_DEFAULTS['operationtype']))
        usergroup_ids = set(int(grp['usrgrpid']) for opmessage_grp in opmessage_groups for grp in opmessage_grp)

        self.usergroups = ZabbixUserGroupContainer.from_zabbix_ids(self._zapi, list(usergroup_ids), resolve_users=False)

    def refresh(self, **init_kwargs):
        params = dict(filter={'name': self.name}, **self.QUERY_BASE)
        self._api_response = self._call_zapi('action.get', params=params)
        zabbix_object = self.parse_zabbix_get_result(self._api_response)
        self.init(zabbix_object, **init_kwargs)

    def create(self, dc_name, create_mgmt_data):
        params = self._generate_create_params(dc_name, create_mgmt_data)
        self._api_response = self._call_zapi('action.create', params=params)
        self.zabbix_id = self.parse_zabbix_create_result(self._api_response, 'actionids')
        self.zabbix_object = params  # TODO: maybe we should rather call refresh()

        return self.CREATED

    def update(self, dc_name, update_mgmt_data):
        params = self._generate_update_params(dc_name, update_mgmt_data)
        self._api_response = self._call_zapi('action.update', params=params)
        assert self.zabbix_id == int(self.parse_zabbix_update_result(self._api_response, 'actionids'))
        self.zabbix_object.update(params)  # TODO: maybe we should rather call refresh()

        return self.UPDATED

    def delete(self):
        assert self.zabbix_id, 'Cannot delete Action without actionid'
        self._api_response = self._call_zapi('action.delete', params=[self.zabbix_id])
        assert self.zabbix_id == int(self.parse_zabbix_delete_result(self._api_response, 'actionids'))
        self.reset()

        return self.DELETED

    @property
    def name_without_dc_prefix(self):
        return self.trans_dc_qualified_name(self.name, from_zabbix=True)

    @property
    def as_mgmt_data(self):
        assert self.zabbix_id, 'Cannot display Action without actionid'
        assert self.usergroups is not None, 'Cannot display Action without usergroups'

        data = {
            'hostgroups': [],
            'hostgroups_created': [],
            'usergroups': [usergroup.name_without_dc_prefix for usergroup in self.usergroups],
        }

        for hostgroup in self.hostgroups:
            visible_hostgroup_name = hostgroup.name_without_dc_prefix
            data['hostgroups'].append(visible_hostgroup_name)

            if hostgroup.new:
                data['hostgroups_created'].append(visible_hostgroup_name)

        for zbx_key, mgmt_key, transform_fun in self._BASE_PARAMS_MAPPING:
            data[mgmt_key] = transform_fun(self.zabbix_object[zbx_key], from_zabbix=True)

        return data
