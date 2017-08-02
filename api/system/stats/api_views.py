from django.core.cache import cache
from django.utils.encoding import force_text
from django.utils.timezone import now

from api.api_views import APIView
from api.task.response import SuccessTaskResponse
from vms.models import Dc, Node, Vm


class SystemStatsView(APIView):
    """api.system.stats.views.system_stats"""
    _cache_key = 'system_stats'
    dc_bound = False

    @classmethod
    def get_stats(cls, from_cache=True, cache_timeout=30):
        if from_cache:
            res = cache.get(cls._cache_key)

            if res:
                return res

        created = now()
        dcs = {force_text(label).lower(): Dc.objects.filter(access=access).count()
               for access, label in Dc.ACCESS}
        nodes = {force_text(label).lower(): Node.objects.filter(status=status).count()
                 for status, label in Node.STATUS_DB}
        vms = {
            'notcreated': Vm.objects.filter(status__in=(Vm.NOTCREATED, Vm.NOTREADY_NOTCREATED, Vm.CREATING,
                                                        Vm.DEPLOYING_START, Vm.DEPLOYING_FINISH,
                                                        Vm.DEPLOYING_DUMMY)).count(),
            'stopped': Vm.objects.filter(status__in=(Vm.STOPPED, Vm.NOTREADY_STOPPED)).count(),
            'running': Vm.objects.filter(status__in=(Vm.RUNNING, Vm.STOPPING, Vm.NOTREADY_RUNNING)).count(),
            'frozen': Vm.objects.filter(status__in=(Vm.FROZEN, Vm.NOTREADY_FROZEN)).count(),
            'unknown': Vm.objects.filter(status__in=(Vm.NOTREADY, Vm.ERROR)).count(),
        }

        res = {
            'created': created,
            'dcs': dcs,
            'dcs_total': sum(dcs.values()),
            'nodes': nodes,
            'nodes_total': sum(nodes.values()),
            'vms': vms,
            'vms_total': sum(vms.values()),
        }
        cache.set(cls._cache_key, res, cache_timeout)

        return res

    def get(self):
        return SuccessTaskResponse(self.request, self.get_stats(), dc_bound=self.dc_bound)
