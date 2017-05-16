# -*- coding: UTF-8 -*-
from celery.utils.log import get_task_logger

from api.mon.utils import MonInternalTask
from que.erigonesd import cq

logger = get_task_logger(__name__)


@cq.task(name='api.mon.base.tasks.mon_user_group_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_group_changed(*args, **kwargs):
    print args
    print kwargs
    # z.zapi.usergroup.get({'search': {'name': ":dc_name:*"}, 'searchWildcardsEnabled': True})

    pass  # TODO


@cq.task(name='api.mon.base.tasks.mon_user_changed', base=MonInternalTask)  # logging will be done separately
def mon_user_changed(*args, **kwargs):
    print args
    print kwargs
    pass  # TODO
