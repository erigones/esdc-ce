from logging import getLogger

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from gui.utils import collect_view_data, get_pager

from gui.decorators import profile_required, admin_required
from api.decorators import setting_required
from api.utils.views import call_api_view
from api.mon.base.views import mon_alert_list

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
@profile_required
def alert_list(request):
    context = collect_view_data(request, 'mon_alert_list')

    method = 'GET'

    logger.info('Calling API view %s mon_alert_list(%s, data=%s) by user %s in DC %s',
                method, request, None, request.user, request.dc)
    res = call_api_view(request, method, mon_alert_list, disable_throttling=True)

    if res.status_code in (200, 201) and method == 'GET' and res.data['result'] is not None:
        context['alerts'] = context['pager'] = get_pager(request, res.data['result'])

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
