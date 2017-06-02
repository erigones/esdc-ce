# -*- coding: UTF-8 -*-
from celery.utils.log import get_task_logger

from api.mon.utils import MonInternalTask
from que.erigonesd import cq
from api.mon.zabbix import getZabbix

logger = get_task_logger(__name__)


@cq.task(name='api.mon.base.tasks.mon_user_group_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_group_changed(task_id, sender, group_name=None, dc_name=None, *args, **kwargs):
    from vms.models import Dc, Vm
    from gui.models import Role, User
    if dc_name and group_name:
        dc = Dc.objects.get_by_name(dc_name)
        zabbix = getZabbix(dc)
        # particular group under dc changed
        q = Role.objects.filter(name=group_name)
        if q.exists():
            group = q.get()
            logger.debug('going to update %s from %s', (group.name, dc.name))
            zabbix.synchronize_user_group(group=group)
        else:
            logger.debug('going to delete %s from %s', (group_name, dc.name))
            zabbix.delete_user_group(name=group_name)
    elif dc_name:
        # dc changed
        try:
            dc = Dc.objects.get_by_name(dc_name)
        except Exception:
            raise NotImplementedError(
                "TODO")  # When DC is deleted, we lose the access to the zabbix and therefore we don't know what to do
        else:
            zabbix = getZabbix(dc)
            zabbix.synchronize_user_group(dc_as_group=True)  # DC name is implied by the zabbix instance

    elif group_name:
        # group under all dcs changed
        # This is an expensive operation, but it's related only to a few superadmin related cases
        q = Role.objects.filter(name=group_name)
        if q.exists():
            group = q.get()
            # group exists, we have to update where it should be
            for dc in group.dc_set.all():
                logger.debug('going to update %s from %s', (group.name, dc.name))
                zabbix = getZabbix(dc)
                zabbix.synchronize_user_group(group=group)
            # and delete where it shouldn't be
            for dc in Dc.objects.exclude(roles=group):  # TODO this is quite expensive and I would like to avoid this
                logger.debug('going to delete %s from %s', (group.name, dc.name))
                zabbix = getZabbix(dc)
                zabbix.delete_user_group(name=group_name)
        else:
            # group does not exist-> remove from all dcs as we don't know where it was
            for dc in Dc.objects.all():
                logger.debug('going to delete %s from %s', (group_name, dc.name))
                zabbix = getZabbix(dc)
                zabbix.delete_user_group(name=group_name)

    else:
        raise AssertionError("either group name or dc name has to be defined")


@cq.task(name='api.mon.base.tasks.mon_user_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_changed(task_id, sender, user_name, dc_name=None, affected_groups=(), *args, **kwargs):
    """
    When  removing user from a group, we don't know frmo which one we removed it.
    We have to get all groups to which the user belongs to, get their respective zabbix apis
    and remove the complement(difference) of the sets of all mgmt groups and the zabbix user groups

    """
    from vms.models import Dc, Vm
    from gui.models import Role, User

    q = User.objects.filter(username=user_name)
    if q.exists():
        user = q.get()
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = getZabbix(dc)
            zabbix.synchronize_user(user=user)
        elif affected_groups:
            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = getZabbix(dc)
                zabbix.synchronize_user(user=user)
        else:
            for dc in Dc.objects.filter(roles__user=user):
                zabbix = getZabbix(dc)
                zabbix.synchronize_user(user=user)
    else:
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = getZabbix(dc)
            zabbix.delete_user(name=user_name)
        elif affected_groups:
            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = getZabbix(dc)
                zabbix.delete_user(name=user_name)
        else:
            for dc in Dc.objects.all():  # Nasty
                zabbix = getZabbix(dc)
                zabbix.delete_user(name=user_name)
