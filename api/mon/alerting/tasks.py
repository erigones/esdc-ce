# -*- coding: UTF-8 -*-
from celery.utils.log import get_task_logger
from zabbix_api import ZabbixAPIException

from api.mon.utils import MonInternalTask
from que.erigonesd import cq
from api.mon import get_monitoring, MonitoringError

from vms.models import Dc
from gui.models import Role, User

__all__ = ('mon_user_group_changed', 'mon_user_changed')

logger = get_task_logger(__name__)


def _user_group_changed(group_name, dc_name):
    if dc_name and group_name:  # Particular group under dc changed
        dc = Dc.objects.get_by_name(dc_name)
        zabbix = get_monitoring(dc)

        try:
            group = Role.objects.get(dc=dc, name=group_name)
        except Role.DoesNotExist:
            logger.debug('Going to delete %s from %s.', group_name, dc.name)
            zabbix.delete_user_group(name=group_name)
        else:
            logger.debug('Going to update %s from %s.', group.name, dc.name)
            zabbix.synchronize_user_group(group=group)
    elif dc_name:  # Something about dc changed

        try:
            dc = Dc.objects.get_by_name(dc_name)
        except Dc.DoesNotExist:
            raise NotImplementedError('TODO DC deletion hook is not implemented')
            # When DC is deleted, we lose the access to the zabbix and therefore we don't know what to do
            # We have to provide information about zabbix connection so that we can delete related information in zabbix
        else:
            zabbix = get_monitoring(dc)
            zabbix.synchronize_user_group(dc_as_group=True)  # DC name is implied by the zabbix instance
    elif group_name:  # A group under unknown dc changed
        # This is an expensive operation, but not called often

        try:
            group = Role.objects.get(name=group_name)
        except Role.DoesNotExist:
            # group does not exist-> remove from all dcs as we don't know where it was

            for dc in Dc.objects.all():
                logger.debug('Going to delete %s from %s.', group_name, dc.name)
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user_group(name=group_name)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and group %s because it crashed.",
                                     dc.name, group_name)
                    mon_user_group_changed.call(group_name=group_name, dc_name=dc.name)

        else:
            related_dcs = Dc.objects.filter(roles=group)
            unrelated_dcs = Dc.objects.exclude(id__in=related_dcs)

            for dc in related_dcs:
                logger.debug('Going to update %s from %s.', group.name, dc.name)
                zabbix = get_monitoring(dc)
                try:
                    zabbix.synchronize_user_group(group=group)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and group %s because it crashed.",
                                     dc.name, group_name)
                    mon_user_group_changed.call(group_name=group_name, dc_name=dc.name)

            for dc in unrelated_dcs:  # TODO this is quite expensive and I would like to avoid this somehow
                logger.debug('Going to delete %s from %s.', group.name, dc.name)
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user_group(name=group_name)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and group %s because it crashed.",
                                     dc.name, group_name)
                    mon_user_group_changed.call(group_name=group_name, dc_name=dc.name)

    else:
        raise AssertionError('Either group name or dc name has to be defined.')


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_user_group_changed',
         base=MonInternalTask,  # logging will be done separately
         max_retries=1,  # if there is a race, one retry may be enough
         default_retry_delay=5,  # it's shorter so that we don't lose context
         bind=True)
def mon_user_group_changed(self, task_id, sender, group_name=None, dc_name=None, *args, **kwargs):
    logger.info("mon_user_group_changed task has started with dc_name %s, and group_name %s",
                dc_name, group_name)
    try:
        _user_group_changed(group_name, dc_name)
    except (ZabbixAPIException, MonitoringError) as exc:
        logger.exception("mon_user_group_changed task crashed, it's going to be retried")
        self.retry(exc=exc)


def _user_changed(user_name, dc_name, affected_groups):
    try:
        user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = get_monitoring(dc)
            logger.debug('Going to delete user with name %s in zabbix %s for dc %s.', user_name, zabbix, dc)
            zabbix.delete_user(name=user_name)
        elif affected_groups:
            logger.debug('Going to delete user with name %s '
                         'from zabbixes related to groups %s.', user_name, affected_groups)

            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user(name=user_name)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and user %s because it crashed.",
                                     dc.name, user_name)
                    mon_user_changed.call(user_name=user_name, dc_name=dc.name)
        else:
            logger.debug('As we don\'t know where does the user %s belonged to, '
                         'we are trying to delete it from all available zabbixes.', user_name)

            for dc in Dc.objects.all():  # Nasty
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user(name=user_name)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and user %s because it crashed.",
                                     dc.name, user_name)
                    mon_user_changed.call(user_name=user_name, dc_name=dc.name)
    else:
        if dc_name:
            dc = Dc.objects.get_by_name(dc_name)
            zabbix = get_monitoring(dc)
            logger.debug('Going to create/update user %s in zabbix %s for dc %s.', user_name, zabbix, dc)
            zabbix.synchronize_user(user=user)
        elif affected_groups:
            logger.debug('Going to create/update user %s in zabbixes related to groups %s.', user_name,
                         affected_groups)

            for dc in Dc.objects.filter(roles__in=affected_groups):
                zabbix = get_monitoring(dc)
                try:
                    zabbix.synchronize_user(user=user)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and user %s because it crashed.",
                                     dc.name, user_name)
                    mon_user_changed.call(user_name=user_name, dc_name=dc.name)

        else:
            logger.debug('Going to create/update user %s '
                         'in zabbixes related to all groups to which the user is related to.', user_name)

            for dc in Dc.objects.filter(roles__user=user):
                zabbix = get_monitoring(dc)
                try:
                    zabbix.synchronize_user(user=user)
                except (ZabbixAPIException, MonitoringError):
                    # we will let it try again in a separate task and not crash this one
                    logger.exception("Creating a separate task for dc %s and user %s because it crashed.",
                                     dc.name, user_name)
                    mon_user_changed.call(user_name=user_name, dc_name=dc.name)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_user_changed',
         base=MonInternalTask,  # logging will be done separately
         max_retries=1,  # if there is a race, one retry may be enough
         default_retry_delay=5,  # it's shorter so that we don't lose context
         bind=True)
def mon_user_changed(self, task_id, sender, user_name, dc_name=None, affected_groups=(), *args, **kwargs):
    """
    When a user is removed from a group, this task doesn't know from which group the user was removed.
    We have to get all groups to which the user belongs to, get their respective zabbix apis
    and remove the complement(difference) of the sets of all relevant mgmt groups and the zabbix user groups
    """
    logger.info("mon_user_changed task has started with dc_name %s, user_name %s and affected_groups %s",
                dc_name, user_name, affected_groups)
    try:
        _user_changed(user_name, dc_name, affected_groups)
    except (ZabbixAPIException, MonitoringError) as exc:
        logger.exception("mon_user_changed task crashed, it's going to be retried")
        self.retry(exc=exc)
