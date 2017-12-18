# -*- coding: UTF-8 -*-
from django.utils.six import text_type
from celery.utils.log import get_task_logger
from zabbix_api import ZabbixAPIException

from api.task.utils import mgmt_task
from api.mon import get_monitoring, MonitoringError
from api.mon.utils import MonInternalTask
from que.erigonesd import cq
from que.exceptions import MgmtTaskException
from que.mgmt import MgmtTask

from vms.models import Dc, Vm, Node
from gui.models import Role, User

__all__ = ('mon_user_group_changed', 'mon_user_changed', 'mon_alert_list')

logger = get_task_logger(__name__)


def _user_group_changed(group_name, dc_name):  # noqa: R701
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
            # TODO: to be implemented
            logger.warning('DC deletion hook is not implemented -> manual cleanup in Zabbix is required')
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
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and group %s because it crashed.',
                                 dc.name, group_name)
                    mon_user_group_changed.call(sender='parent mon_user_group_changed',
                                                group_name=group_name,
                                                dc_name=dc.name)

        else:
            related_dcs = Dc.objects.filter(roles=group)
            unrelated_dcs = Dc.objects.exclude(id__in=related_dcs)

            for dc in related_dcs:
                logger.debug('Going to update %s from %s.', group.name, dc.name)
                zabbix = get_monitoring(dc)
                try:
                    zabbix.synchronize_user_group(group=group)
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and group %s because it crashed.',
                                 dc.name, group_name)
                    mon_user_group_changed.call(sender='parent mon_user_group_changed',
                                                group_name=group_name,
                                                dc_name=dc.name)

            for dc in unrelated_dcs:  # TODO this is quite expensive and I would like to avoid this somehow
                logger.debug('Going to delete %s from %s.', group.name, dc.name)
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user_group(name=group_name)
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and group %s because it crashed.',
                                 dc.name, group_name)
                    mon_user_group_changed.call(sender='parent mon_user_group_changed',
                                                group_name=group_name,
                                                dc_name=dc.name)

    else:
        raise AssertionError('Either group name or dc name has to be defined.')


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_user_group_changed',
         base=MonInternalTask,  # logging will be done separately
         max_retries=1,  # if there is a race, one retry may be enough
         default_retry_delay=5,  # it's shorter so that we don't lose context
         bind=True)
def mon_user_group_changed(self, task_id, sender, group_name=None, dc_name=None, *args, **kwargs):
    logger.info('mon_user_group_changed task has started with dc_name %s, and group_name %s',
                dc_name, group_name)
    try:
        _user_group_changed(group_name, dc_name)
    except (ZabbixAPIException, MonitoringError) as exc:
        logger.exception(exc)
        logger.error('mon_user_group_changed task crashed, it\'s going to be retried')
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
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and user %s because it crashed.',
                                 dc.name, user_name)
                    mon_user_changed.call(sender='parent mon_user_changed',
                                          user_name=user_name,
                                          dc_name=dc.name)
        else:
            logger.debug('As we don\'t know where does the user %s belonged to, '
                         'we are trying to delete it from all available zabbixes.', user_name)

            for dc in Dc.objects.all():  # Nasty
                zabbix = get_monitoring(dc)
                try:
                    zabbix.delete_user(name=user_name)
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and user %s because it crashed.',
                                 dc.name, user_name)
                    mon_user_changed.call(sender='parent mon_user_changed',
                                          user_name=user_name,
                                          dc_name=dc.name)
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
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and user %s because it crashed.',
                                 dc.name, user_name)
                    mon_user_changed.call(sender='parent mon_user_changed', user_name=user_name, dc_name=dc.name)

        else:
            logger.debug('Going to create/update user %s '
                         'in zabbixes related to all groups to which the user is related to.', user_name)

            for dc in Dc.objects.filter(roles__user=user):
                zabbix = get_monitoring(dc)
                try:
                    zabbix.synchronize_user(user=user)
                except (ZabbixAPIException, MonitoringError) as exc:
                    logger.exception(exc)
                    # we will let it try again in a separate task and not crash this one
                    logger.error('Creating a separate task for dc %s and user %s because it crashed.',
                                 dc.name, user_name)
                    mon_user_changed.call(sender='parent mon_user_changed', user_name=user_name, dc_name=dc.name)


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
    logger.info('mon_user_changed task has started with dc_name %s, user_name %s and affected_groups %s',
                dc_name, user_name, affected_groups)
    try:
        _user_changed(user_name, dc_name, affected_groups)
    except (ZabbixAPIException, MonitoringError) as exc:
        logger.exception(exc)
        logger.error('mon_user_changed task crashed, it\'s going to be retried')
        self.retry(exc=exc)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.base.tasks.mon_all_groups_sync', base=MonInternalTask)
def mon_all_groups_sync(task_id, sender, dc_name=None, *args, **kwargs):
    if dc_name:
        for group in Role.objects.filter(dc__name=dc_name):
            mon_user_group_changed.call(sender='mon_all_groups_sync', dc_name=dc_name, group_name=group.name)
        mon_user_group_changed.call(sender='mon_all_groups_sync', dc_name=dc_name)  # one special case (owner group)
    else:
        # super heavy
        for group in Role.objects.all():
            mon_user_group_changed.call(sender='mon_all_groups_sync', group_name=group.name)
        for dc in Dc.objects.all():  # owner groups
            mon_user_group_changed.call(sender='mon_all_groups_sync', dc_name=dc.name)


# noinspection PyUnusedLocal
@cq.task(name='api.mon.alerting.tasks.mon_alert_list', base=MgmtTask)
@mgmt_task()
def mon_alert_list(task_id, dc_id, dc_bound=True, node_uuids=None, vm_uuids=None, since=None, until=None, last=None,
                   show_events=True, **kwargs):
    """
    Return list of alerts available in Zabbix.
    """
    dc = Dc.objects.get_by_id(int(dc_id))
    alerts = []
    empty = ()

    if dc_bound:
        nodes_qs = empty
        vms_qs = Vm.objects.filter(dc=dc, slavevm__isnull=True).exclude(status=Vm.NOTCREATED)

        if vm_uuids is not None:
            vms_qs = vms_qs.filter(uuid__in=vm_uuids)

        mon = get_monitoring(dc)
        mon_vms_nodes_map = {mon.ezx.connection_id: (mon, vms_qs, nodes_qs)}

    else:
        assert dc.is_default()

        if vm_uuids is None and node_uuids is None:
            nodes_qs = Node.objects.all()
            vms_qs = Vm.objects.select_related('dc').filter(slavevm__isnull=True).exclude(status=Vm.NOTCREATED)  # All
        elif vm_uuids is not None and node_uuids is None:
            nodes_qs = empty
            vms_qs = Vm.objects.select_related('dc').filter(uuid__in=vm_uuids).exclude(status=Vm.NOTCREATED)  # Filtered
        elif vm_uuids is None and node_uuids is not None:
            nodes_qs = Node.objects.filter(uuid__in=node_uuids)
            vms_qs = empty
        elif vm_uuids is not None and node_uuids is not None:
            nodes_qs = Node.objects.filter(uuid__in=node_uuids)
            vms_qs = Vm.objects.select_related('dc').filter(uuid__in=vm_uuids).exclude(status=Vm.NOTCREATED)  # Filtered
        else:
            raise AssertionError('Unexpected condition in mon_alert_list')

        mon_default_dc = get_monitoring(dc)
        mon_vms_nodes_map = {mon_default_dc.ezx.connection_id: (mon_default_dc, [], nodes_qs)}

        for vm in vms_qs:
            mon = get_monitoring(vm.dc)

            if mon.enabled:
                connection_id = mon.ezx.connection_id

                if connection_id not in mon_vms_nodes_map:
                    mon_vms_nodes_map[connection_id] = (mon, [], empty)

                mon_vms_nodes_map[connection_id][1].append(vm)

    for mon, vms, nodes in mon_vms_nodes_map.values():
        logger.info('Fetching monitoring alerts from Zabbix server: %s', mon.ezx.server)
        try:
            alerts.extend(mon.alert_list(vms=vms, nodes=nodes, since=since, until=until, last=last,
                                         show_events=show_events))
        except MonitoringError as exc:
            raise MgmtTaskException(text_type(exc))

    return alerts
