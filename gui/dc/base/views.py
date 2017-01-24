from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings

from vms.models import Dc
from gui.decorators import staff_required, ajax_required, admin_required, profile_required
from gui.utils import collect_view_data, redirect, get_query_string, Messages
from gui.dc.base.utils import get_dcs_extended
from gui.dc.base.forms import DcForm, DcSettingsForm, DefaultDcSettingsForm
from api.dc.utils import get_dc_or_404


def _dc_settings_msg_updated(request):
    messages.success(request, _('Datacenter settings were successfully updated'))


def _dc_settings_msg_error(context):
    msg = Messages()
    msg.error(_('Datacenter settings were not updated. Please correct errors below'))
    context['error'] = msg


@login_required
@admin_required
@profile_required
def dc_list(request):
    """
    Datacenter management.
    """
    context = collect_view_data(request, 'dc_list')
    context['can_edit'] = can_edit = request.user.is_staff  # DC owners have read-only rights

    if can_edit:
        pr = ('roles',)
        context['all'] = _all = bool(request.GET.get('all', False))
        context['form'] = DcForm(request, None, initial={'access': Dc.PRIVATE, 'owner': request.user.username})
        context['settings_form'] = DcSettingsForm(request, None)
        context['can_add'] = settings.VMS_DC_ENABLED
        context['colspan'] = 9
    else:
        _all = False
        pr = None  # Groups are only visible by SuperAdmins
        context['colspan'] = 8

    context['qs'] = get_query_string(request, all=_all).urlencode()
    context['dcs'] = get_dcs_extended(request, pr=pr)

    return render(request, 'gui/dc/dc_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_form(request):
    """
    Ajax page for creating or updating datacenter.
    """
    if request.POST['action'] == 'create':
        dc = None
    else:
        dc = get_dc_or_404(request, request.POST['name'], api=False)

    form = DcForm(request, dc, request.POST)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data.get('name'),))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            messages.success(request, _('Datacenter settings were successfully updated'))
            return redirect('dc_list', query_string=request.GET)

    return render(request, 'gui/dc/dc_form.html', {'form': form})


@login_required
@staff_required
@ajax_required
@require_POST
def dc_settings_form(request):
    """
    Ajax page for changing advanced datacenter settings.
    """
    dc = get_dc_or_404(request, request.POST['dc'], api=False)
    form = DcSettingsForm(request, dc, request.POST)
    context = {'form': form}

    if form.is_valid():
        status = form.save(args=(dc.name,))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            _dc_settings_msg_updated(request)
            return redirect('dc_list', query_string=request.GET)

    _dc_settings_msg_error(context)

    return render(request, 'gui/dc/dc_settings_form.html', context)


def _dc_settings_table(request, data=None):
    """Create basic context for rendering dc_settings_table.html"""
    dc = request.dc
    _all = bool(request.GET.get('all', False))

    if _all:
        form_class = DefaultDcSettingsForm
    else:
        form_class = DcSettingsForm

    form = form_class(request, dc, data=data, init=True, table=True, disable_globals=_all and not dc.is_default())

    return {
        'all': _all,
        'form': form,
        'qs': get_query_string(request, all=_all).urlencode(),
        'msg_global_setting': _('Global setting')
    }


@login_required
@staff_required
def dc_settings(request):
    """
    Own page for datacenter settings. When used in the default DC we display all Danube Cloud settings.
    """
    context = collect_view_data(request, 'dc_settings')
    context.update(_dc_settings_table(request))
    context['form'].set_mon_zabbix_server_login_error()

    return render(request, 'gui/dc/dc_settings.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_settings_table(request):
    """
    Ajax page for changing all datacenter settings.
    """
    context = _dc_settings_table(request, data=request.POST)
    form = context['form']

    if form.is_valid():
        status = form.save(args=(request.dc.name,), action='update')
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            _dc_settings_msg_updated(request)
            return redirect('dc_settings', query_string=request.GET)

    _dc_settings_msg_error(context)
    form.set_mon_zabbix_server_login_error()

    return render(request, 'gui/dc/dc_settings_table.html', context)
