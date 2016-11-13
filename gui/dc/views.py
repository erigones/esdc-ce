from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.conf import settings

from gui.decorators import staff_required, ajax_required
from gui.utils import redirect
from gui.dc.forms import DcSwitch

# Required for urls.py
# noinspection PyUnresolvedReferences
from gui.dc.base.views import dc_list, dc_form
# The main DC views are in the base folder
# The other views here are mostly DC related helper views


@login_required
@ajax_required
@require_POST
def dc_switch_form(request):
    """
    Ajax page for changing current working datacenter.
    """
    form = DcSwitch(request, request.POST, prefix='dc')

    if form.is_valid():
        if form.save():
            return redirect(form.get_referrer() or settings.LOGIN_REDIRECT_URL)
        else:
            return HttpResponse(None, status=204)

    return render(request, 'gui/dc/dc_switch_form.html', {'dcs_form': form})


def dc_switch(request, dc_name):
    """Helper for switching datacenter. Used in redirect views"""
    if request.dc.name != dc_name:
        form = DcSwitch(request, {'name': dc_name})
        if form.is_valid():
            if form.save():
                request.dc = request.user.default_dc
                return True
        else:
            raise Http404('Datacenter not found')

    return False


@login_required
@staff_required
def dc_vm_details(request, dc, hostname):
    """
    Switch current datacenter and redirect vm_details page.
    """
    dc_switch(request, dc)

    return redirect('vm_details', hostname=hostname)
