from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse

from gui.decorators import staff_required, ajax_required, admin_required, profile_required
from gui.utils import collect_view_data, redirect, get_query_string
from gui.dc.template.forms import TemplateForm
from gui.models.permission import TemplateAdminPermission
from vms.models import VmTemplate


@login_required
@admin_required
@profile_required
def dc_template_list(request):
    """
    VmTemplate<->Dc management.
    """
    user, dc = request.user, request.dc
    vmts = VmTemplate.objects.order_by('name')
    context = collect_view_data(request, 'dc_template_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, TemplateAdminPermission.name)
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['deleted'] = _deleted = can_edit and request.GET.get('deleted', False)
    context['qs'] = get_query_string(request, all=_all, deleted=_deleted).urlencode()

    if _deleted:
        vmts = vmts.exclude(access=VmTemplate.INTERNAL)
    else:
        vmts = vmts.exclude(access__in=VmTemplate.INVISIBLE)

    if _all:
        context['templates'] = vmts.select_related('owner', 'dc_bound').prefetch_related('dc').all()
    else:
        context['templates'] = vmts.select_related('owner', 'dc_bound').filter(dc=dc)

    if is_staff:
        context['form'] = TemplateForm(request, vmts)

        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(vmts.exclude(dc=dc).values_list('pk', flat=True))
        else:
            context['can_add'] = vmts.exclude(dc=dc).count()

    return render(request, 'gui/dc/template_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_template_form(request):
    """
    Ajax page for attaching and detaching templates.
    """
    form = TemplateForm(request, VmTemplate.objects.all().order_by('name'), request.POST)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_template_list', query_string=request.GET)

    return render(request, 'gui/dc/template_form.html', {'form': form})
