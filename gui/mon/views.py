import json

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render

from gui.mon.forms import BaseAlertFilterForm
from gui.utils import collect_view_data
from gui.decorators import ajax_required, profile_required, admin_required
from api.decorators import setting_required
from api.utils.views import call_api_view
from api.mon.alerting.views import mon_alert_list


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def mon_server_redirect(request):
    """
    Monitoring management.
    """
    return redirect(request.dc.settings.MON_ZABBIX_SERVER)


@login_required
@admin_required
@ajax_required
@require_POST
def alert_list_table(request):
    context = collect_view_data(request, 'mon_alert_list')

    try:
        api_data = json.loads(request.POST.get('alert_filter', None))
    except (ValueError, TypeError):
        context['error'] = 'Unexpected error: could not parse alert filter.'
    else:
        context['alert_filter'] = api_data
        res = call_api_view(request, 'GET', mon_alert_list, data=api_data)

        if res.status_code == 200:
            context['alerts'] = res.data['result']
        elif res.status_code == 201:
            context['error'] = 'Unexpected error: got into an API loop.'
        else:
            context['error'] = res.data.get('result', {}).get('error', res.data)

    return render(request, 'gui/mon/alert_table.html', context)


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def alert_list(request):
    context = collect_view_data(request, 'mon_alert_list')
    context['filters'] = form = BaseAlertFilterForm(request, request.GET.copy())
    context['init'] = True

    if form.is_valid() and form.api_data is not None:  # new visit, or form submission
        context['alert_filter'] = form.api_data
        context['alert_filter_ok'] = True
    else:
        context['alert_filter_ok'] = False  # Do not run javascript API TASKs!

    return render(request, 'gui/mon/alert_list.html', context)


@login_required
@admin_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED')
def action_list(request):
    context = collect_view_data(request, 'mon_action_list')

    return render(request, 'gui/mon/action_list.html', context)
