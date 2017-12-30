from django.utils.translation import ugettext_noop as _

from api.mon.constants import MON_OBJ_NOTHING, MON_OBJ_CREATED, MON_OBJ_UPDATED, MON_OBJ_DELETED

MON_ACTIONS = {
    MON_OBJ_NOTHING: '',
    MON_OBJ_CREATED: 'created',
    MON_OBJ_UPDATED: 'updated',
    MON_OBJ_DELETED: 'deleted',
}

MON_ACTION_DETAIL = '{mon_object} "{name}" was successfully {action}'

MON_ACTION_DETAIL_DC = MON_ACTION_DETAIL + ' in datacenter "{dc_name}"'


LOG_MONDEF_UPDATE = _('Update server monitoring definition')

LOG_MON_NODE_UPDATE = _('Sync compute node monitoring host')
LOG_MON_NODE_DELETE = _('Delete compute node monitoring host')

LOG_MON_VM_UPDATE = _('Sync server monitoring host')
LOG_MON_VM_DELETE = _('Delete server monitoring host')


MON_OBJ_USER = 'Monitoring user'

LOG_MON_USER_CREATE = _('Create monitoring user')
LOG_MON_USER_UPDATE = _('Update monitoring user')
LOG_MON_USER_DELETE = _('Delete monitoring user')

MON_USER_ACTION_MESSAGES = {
    MON_OBJ_NOTHING: None,
    MON_OBJ_CREATED: LOG_MON_USER_CREATE,
    MON_OBJ_UPDATED: LOG_MON_USER_UPDATE,
    MON_OBJ_DELETED: LOG_MON_USER_DELETE,
}


MON_OBJ_USERGROUP = 'Monitoring usergroup'

LOG_MON_USERGROUP_CREATE = _('Create monitoring usergroup')
LOG_MON_USERGROUP_UPDATE = _('Update monitoring usergroup')
LOG_MON_USERGROUP_DELETE = _('Delete monitoring usergroup')

MON_USERGROUP_ACTION_MESSAGES = {
    MON_OBJ_NOTHING: None,
    MON_OBJ_CREATED: LOG_MON_USERGROUP_CREATE,
    MON_OBJ_UPDATED: LOG_MON_USERGROUP_UPDATE,
    MON_OBJ_DELETED: LOG_MON_USERGROUP_DELETE,
}


MON_OBJ_HOSTGROUP = 'Monitoring hostgroup'

LOG_MON_HOSTGROUP_CREATE = _('Create monitoring hostgroup')
LOG_MON_HOSTGROUP_UPDATE = _('Update monitoring hostgroup')
LOG_MON_HOSTGROUP_DELETE = _('Delete monitoring hostgroup')


MON_OBJ_ACTION = 'Monitoring action'

LOG_MON_ACTION_CREATE = _('Create monitoring action')
LOG_MON_ACTION_UPDATE = _('Update monitoring action')
LOG_MON_ACTION_DELETE = _('Delete monitoring action')


def get_mon_action_detail(mon_object, obj_action_result, name, dc_name=None):
    if dc_name:
        detail_msg = MON_ACTION_DETAIL_DC
    else:
        detail_msg = MON_ACTION_DETAIL

    return detail_msg.format(mon_object=mon_object, action=MON_ACTIONS[obj_action_result], name=name, dc_name=dc_name)
