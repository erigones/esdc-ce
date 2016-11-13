from api.task.log import get_tasklog as _get_tasklog
from api.task.task_log import TaskLogView
from gui.utils import get_order_by
from gui.tasklog.forms import BaseTaskLogFilterForm


def get_tasklog(request, context, form_cls=BaseTaskLogFilterForm, base_query=None, **kwargs):
    """
    Task log with filters.
    """
    context['filters'] = form = form_cls(request.GET.copy())

    if form.is_valid() and form.has_changed():
        q = form.get_filters(pending_tasks=context['pending_tasks'])

        if base_query:
            q = base_query & q
    else:
        q = base_query

    context['order_by'], order_by = get_order_by(request, api_view=TaskLogView, db_default=('-time',),
                                                 user_default=('-time',))

    return _get_tasklog(request, q=q, order_by=order_by, **kwargs)
