from logging import getLogger

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from gui.mon.forms import BaseAlertFilterForm
from gui.utils import collect_view_data
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


@login_required
@admin_required
@profile_required
@ajax_required
def alert_list_table(request):
    context = collect_view_data(request, 'mon_alert_list')
    context['show_events'] = False

    if request.GET['show_events'] in ('true', 'on'):
        context['show_events'] = request.GET['show_events']

    method = 'GET'
    logger.info('Calling API view %s mon_alert_list(%s, data=%s) by user %s in DC %s',
                method, request, None, request.user, request.dc)

    res = call_api_view(request, method, mon_alert_list, data=BaseAlertFilterForm.format_data(request.GET))

    if res.status_code in (200, 201) and method == 'GET' and res.data['result'] is not None:
        context['alerts'] = res.data['result']

    return render(request, 'gui/mon/alert_table.html', context)


@login_required
@admin_required
@profile_required
def alert_list(request):
    context = collect_view_data(request, 'mon_alert_list')
    context['filters'] = alert_form = BaseAlertFilterForm(request, request.GET.copy())
    alert_form.full_clean()

    if not alert_form.has_changed() or alert_form.is_valid():  # new visit, or form submission
        context['alert_filter'] = alert_form.api_data
        context['show_events'] = alert_form.api_data['show_events']
    else:
        context['alert_filter'] = None  # Do not run javascript API TASKs!

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
