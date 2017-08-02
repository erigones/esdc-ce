from datetime import timedelta

from celery import states
from django.utils import timezone
from django.db.models import Count

from api import status
from api.api_views import APIView
from api.paginator import get_pager
from api.exceptions import InvalidInput
from api.task.response import TaskSuccessResponse, SimpleTaskResponse
from api.task.log import get_tasklog, get_tasklog_cached
from api.task.utils import get_user_tasks
from api.task.serializers import TaskLogEntrySerializer, TaskLogFilterSerializer
from vms.models import TaskLogEntry


class TaskLogView(APIView):
    """Task log API views"""
    order_by_default = ('-time',)
    order_by_fields = ('time',)

    def get(self):
        """api.task.views.task_log"""
        request = self.request

        if self.data.get('page', None):
            ser = TaskLogFilterSerializer(data=self.data)

            if not ser.is_valid():
                return SimpleTaskResponse(request, ser.errors, status.HTTP_400_BAD_REQUEST)

            q = ser.get_filters(pending_tasks=get_user_tasks(request))
            tasklog_items = get_tasklog(request, q=q, order_by=self.order_by)
            TaskLogEntry.prepare_queryset(tasklog_items)
            pag = get_pager(request, tasklog_items, per_page=100)
            res = pag.paginator.get_response_results(TaskLogEntrySerializer(pag, many=True).data)
        else:
            res = {'results': get_tasklog_cached(request)}

        return TaskSuccessResponse(request, res)

    @staticmethod
    def _get_stats_result(basequery):
        def get_count(state):
            return basequery.filter(status=state).aggregate(count=Count('id')).get('count', 0)

        return {
            'pending': get_count(states.PENDING),
            'revoked': get_count(states.REVOKED),
            'succeeded': get_count(states.SUCCESS),
            'failed': get_count(states.FAILURE),
        }

    def get_stats(self):
        try:
            last = int(self.data.get('last', 86400))
            startime = timezone.now() - timedelta(seconds=last)
        except:
            raise InvalidInput('Invalid "last" parameter')

        qs = get_tasklog(self.request, sr=(), time__gte=startime)
        res = self._get_stats_result(qs)
        res['_last'] = last

        return res

    def get_stats_response(self):
        """api.task.views.task_log_stats"""
        return TaskSuccessResponse(self.request, self.get_stats())
