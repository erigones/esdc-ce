from datetime import datetime
from dateutil.relativedelta import relativedelta

from api.exceptions import InvalidInput, ExpectationFailed
from api.mon.utils import MonInternalTask
from que import TG_DC_UNBOUND


# noinspection PyAbstractClass
class NodeMonInternalTask(MonInternalTask):
    """
    Internal zabbix task for Node objects.
    """
    abstract = True
    setting_required = 'MON_ZABBIX_NODE_SYNC'  # The parent class should look into dc1_settings

    def call(self, *args, **kwargs):
        # node task is not dc-bound
        kwargs['tg'] = TG_DC_UNBOUND
        return super(NodeMonInternalTask, self).call(*args, **kwargs)


def parse_yyyymm(yyyymm, min_value):
    """Process the yyyymm string and return (yyyymm, since, until, current_month) tuple consisting of:
    - validated yyyymm string,
    - since and until datetime objects,
    - current_month boolean.

    Used in SLA views.
    """
    # noinspection PyBroadException
    try:
        yyyymm = str(yyyymm)
        since = datetime(year=int(yyyymm[:4]), month=int(yyyymm[4:]), day=1)
    except:
        raise InvalidInput('Invalid yyyymm')

    now = datetime.now()
    yyyymm = since.strftime('%Y%m')
    current_month = now.strftime('%Y%m') == yyyymm

    if current_month:
        until = now
    else:
        until = since + relativedelta(months=+1)

    if until < min_value or since > now:
        raise ExpectationFailed('Monitoring data not available')

    return yyyymm, since, until, current_month
