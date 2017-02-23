from datetime import timedelta

from django.utils import timezone

from api import status
from api.api_views import APIView
from api.paginator import get_pager
from api.exceptions import InvalidInput
from api.task.response import TaskSuccessResponse, SimpleTaskResponse
from api.task.log import get_tasklog, get_tasklog_cached
from api.task.utils import get_user_tasks
from api.task.serializers import TaskLogEntrySerializer, TaskLogFilterSerializer, TaskLogReportSerializer
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

    def report(self):
        """api.task.views.task_log_report"""
        try:
            startime = timezone.now() - timedelta(seconds=int(self.data.get('last', 86400)))
        except:
            raise InvalidInput('Invalid "last" parameter')

        qs = get_tasklog(self.request, sr=(), time__gte=startime)
        report = TaskLogReportSerializer.get_report(qs)

        return TaskSuccessResponse(self.request, TaskLogReportSerializer(report).data)
