import json
from logging import getLogger

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from gui.mon.forms import BaseAlertFilterForm
from gui.utils import collect_view_data, get_pager
from gui.decorators import ajax_required, profile_required, admin_required
from api.decorators import setting_required
from api.utils.views import call_api_view
from api.mon.alerting.views import mon_alert_list
from api.task.utils import get_task_status

logger = getLogger(__name__)


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def monitoring_server(request):
    """
    Monitoring management.
    """
    return redirect(request.dc.settings.MON_ZABBIX_SERVER)


@login_required
@ajax_required
@profile_required
def alert_list_table(request):
    context = collect_view_data(request, 'mon_alert_list')
    result, status = get_task_status(request.GET['task_id'])

    context['alerts'] = result['result']
    # context['alerts'] = context['pager'] = get_pager(request, result['result'])

    if request.GET['show_events'] in (1, 'on', 'true', 'True'):
        context['show_events'] = True

    return render(request, 'gui/mon/alert_table.html', context)


@login_required
@profile_required
def alert_list(request):
    context = collect_view_data(request, 'mon_alert_list')
    # context['pager'] = get_pager(request, ())
    context['filters'] = alert_form = BaseAlertFilterForm(request, request.GET.copy())
    clean_data = alert_form.clean()

    context['alert_filter'] = json.dumps(clean_data)
    context['show_events'] = clean_data['show_events']

    return render(request, 'gui/mon/alert_list.html', context)


@login_required
@profile_required
def actions_list(request):
    context = collect_view_data(request, 'mon_actions_list')

    return render(request, 'gui/mon/actions_list.html', context)


@login_required
@profile_required
def add_action(request):
    context = collect_view_data(request, 'add_action')

    return render(request, 'gui/mon/add_action_modal.html', context)


@login_required
@profile_required
def action_detail(request, action_id):
    context = collect_view_data(request, 'action_detail')

    return render(request, 'gui/mon/action_detail.html', context)
