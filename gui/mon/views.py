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


def parse_filter(request):
    data = {}

    if 'since' in request.GET:
        data['since'] = request.GET['since']  # TODO: convert to unix epoch

    if 'until' in request.GET:
        data['until'] = request.GET['until']  # TODO: convert to unix epoch

    if 'last' in request.GET:
        data['last'] = request.GET['last']

    if 'vm_hostnames' in request.GET:
        data['vm_hostnames'] = request.GET['vm_hostnames']

    return data


@login_required
@ajax_required
@profile_required
def get_alert_from_zabbix(request):
    context = collect_view_data(request, 'mon_alert_list')
    method = 'GET'
    logger.info('Calling API view %s mon_alert_list(%s, data=%s) by user %s in DC %s',
                method, request, None, request.user, request.dc)

    alert_filter = parse_filter(request)
    res = call_api_view(request, method, mon_alert_list, data=alert_filter)

    if res.status_code in (200, 201) and method == 'GET' and res.data['result'] is not None:
        context['alerts'] = context['pager'] = get_pager(request, res.data['result'])

    return render(request, 'gui/mon/alert_table.html', context)


@login_required
@profile_required
def alert_list(request):
    context = collect_view_data(request, 'mon_alert_list')
    context['filters'] = BaseAlertFilterForm(request.GET.copy())
    context['alert_filter'] = json.dumps(parse_filter(request))

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
