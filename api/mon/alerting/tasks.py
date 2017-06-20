# -*- coding: UTF-8 -*-
from celery.utils.log import get_task_logger

from api.mon.utils import MonInternalTask
from que.erigonesd import cq
from api.mon.zabbix import getZabbix
from vms.models import Dc
from gui.models import Role, User

logger = get_task_logger(__name__)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_user_group_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_group_changed(task_id, sender, group_name=None, dc_name=None, *args, **kwargs):
    if dc_name and group_name:
        dc = Dc.objects.get_by_name(dc_name)
        zabbix = getZabbix(dc)
        # particular group under dc changed
        try:
            group = Role.objects.get(dc=dc, name=group_name)
        except Role.DoesNotExist:
            logger.debug('Going to delete %s from %s.', group_name, dc.name)
            zabbix.delete_user_group(name=group_name)
        else:
            logger.debug('Going to update %s from %s.', group.name, dc.name)
            zabbix.synchronize_user_group(group=group)

    elif dc_name:
        # dc changed
        try:
            dc = Dc.objects.get_by_name(dc_name)
        except Exception:
            raise NotImplementedError("TODO DC deletion hook is not implemented")
            # When DC is deleted, we lose the access to the zabbix and therefore we don't know what to do
            # We have to provide information about zabbix connection so that we can delete related information in zabbix
        else:
            zabbix = getZabbix(dc)
            zabbix.synchronize_user_group(dc_as_group=True)  # DC name is implied by the zabbix instance

    elif group_name:
        # group under all dcs changed
        # This is an expensive operation, but it's related only to a few superadmin related cases
        try:
            group = Role.objects.get(name=group_name)
        except Role.DoesNotExist:
            # group does not exist-> remove from all dcs as we don't know where it was
            for dc in Dc.objects.all():
                logger.debug('Going to delete %s from %s.', group_name, dc.name)
                zabbix = getZabbix(dc)
                zabbix.delete_user_group(name=group_name)
        else:
            related_dcs = Dc.objects.filter(roles=group)
            unrelated_dcs = Dc.objects.exclude(id__in=related_dcs)

            for dc in related_dcs:
                logger.debug('Going to update %s from %s.', group.name, dc.name)
                zabbix = getZabbix(dc)
                zabbix.synchronize_user_group(group=group)

            for dc in unrelated_dcs:  # TODO this is quite expensive and I would like to avoid this somehow
                logger.debug('Going to delete %s from %s.', group.name, dc.name)
                zabbix = getZabbix(dc)
                zabbix.delete_user_group(name=group_name)

    else:
        raise AssertionError("Either group name or dc name has to be defined!")


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_user_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_changed(task_id, sender, user_name, dc_name=None, affected_groups=(), *args, **kwargs):
    """
    When a user is removed from a group, this task doesn't know from which group the user was removed.
    We have to get all groups to which the user belongs to, get their respective zabbix apis
    and remove the complement(difference) of the sets of all relevant mgmt groups and the zabbix user groups
    """
    try:
        user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = getZabbix(dc)
            logger.debug('Going to delete user with name %s in zabbix %s for dc %s.', user_name, zabbix, dc)
            zabbix.delete_user(name=user_name)
        elif affected_groups:
            logger.debug(
                'Going to delete user with name %s from zabbixes related to groups %s.', user_name, affected_groups)
            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = getZabbix(dc)
                zabbix.delete_user(name=user_name)
        else:
            logger.debug('As we don\'t know where does the user %s belonged to, '
                         'we are trying to delete it from all available zabbixes.', user_name)
            for dc in Dc.objects.all():  # Nasty
                zabbix = getZabbix(dc)
                zabbix.delete_user(name=user_name)
    else:
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = getZabbix(dc)
            logger.debug('Going to create/update user %s in zabbix %s for dc %s.', user_name, zabbix, dc)
            zabbix.synchronize_user(user=user)
        elif affected_groups:
            logger.debug('Going to create/update user %s in zabbixes related to groups %s.', user_name, affected_groups)
            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = getZabbix(dc)
                zabbix.synchronize_user(user=user)
        else:
            logger.debug('Going to create/update user %s '
                         'in zabbixes related to all groups to which the user is related to.', user_name)
            for dc in Dc.objects.filter(roles__user=user):
                zabbix = getZabbix(dc)
                zabbix.synchronize_user(user=user)
