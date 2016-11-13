from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from api.task.log import get_tasklog_cached
from gui.tasklog.utils import get_tasklog
from gui.tasklog.forms import TaskLogFilterForm
from gui.decorators import ajax_required, profile_required
from gui.utils import collect_view_data, get_user_tasks, get_pager
from vms.models import TaskLogEntry


@login_required
@profile_required
def index(request):
    """
    Display users tasklog.
    """
    context = collect_view_data(request, 'tasklog')

    tasklog = get_tasklog(request, context, form_cls=TaskLogFilterForm)
    context['tasklog'] = context['pager'] = tasklog_items = get_pager(request, tasklog, per_page=100)
    context['disable_cached_tasklog'] = True
    TaskLogEntry.prepare_queryset(tasklog_items)

    return render(request, 'gui/tasklog/tasklog.html', context)


@login_required
@ajax_required
def cached(request):
    """
    Ajax view for updating cached task log.
    """
    return render(request, 'gui/tasklog/tasklog_cached.html', {
        'tasklog_cached': get_tasklog_cached(request),
        'pending_tasks': get_user_tasks(request),
        'disable_cached_tasklog': request.GET.get('disable_cached_tasklog', False),
    })
