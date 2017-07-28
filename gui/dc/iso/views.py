from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, Http404
from django.http import HttpResponse

from gui.decorators import staff_required, ajax_required, admin_required, profile_required, permission_required
from gui.utils import collect_view_data, reverse, redirect, get_query_string
from gui.models.permission import IsoAdminPermission
from gui.dc.iso.forms import DcIsoForm, AdminIsoForm
from vms.models import Iso


@login_required
@admin_required
@profile_required
def dc_iso_list(request):
    """
    Iso<->Dc management + Iso management.
    """
    user, dc = request.user, request.dc
    isos = Iso.objects.order_by('name')
    context = collect_view_data(request, 'dc_iso_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, IsoAdminPermission.name)
    context['all'] = _all = is_staff and request.GET.get('all', False)
    context['deleted'] = _deleted = can_edit and request.GET.get('deleted', False)
    context['qs'] = qs = get_query_string(request, all=_all, deleted=_deleted).urlencode()

    if _deleted:
        isos = isos.exclude(access=Iso.INTERNAL)
    else:
        isos = isos.exclude(access__in=Iso.INVISIBLE)

    if _all:
        context['isos'] = isos.select_related('owner', 'dc_bound').prefetch_related('dc').all()
    else:
        context['isos'] = isos.select_related('owner', 'dc_bound').filter(dc=dc)

    if is_staff:
        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(isos.exclude(dc=dc).values_list('pk', flat=True))
        else:  # No need for item list
            context['can_add'] = isos.exclude(dc=dc).count()

        context['form_dc'] = DcIsoForm(request, isos)
        context['url_form_dc'] = reverse('dc_iso_form', query_string=qs)

    if can_edit:
        context['url_form_admin'] = reverse('admin_iso_form', query_string=qs)
        context['form_admin'] = AdminIsoForm(request, None, prefix='adm', initial={'owner': user.username,
                                                                                   'access': Iso.PRIVATE,
                                                                                   'dc_bound': not is_staff})

    return render(request, 'gui/dc/iso_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_iso_form(request):
    """
    Ajax page for attaching and detaching isos.
    """
    if 'adm-name' in request.POST:
        prefix = 'adm'
    else:
        prefix = None

    form = DcIsoForm(request, Iso.objects.all().order_by('name'), request.POST, prefix=prefix)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_iso_list', query_string=request.GET)

    # An error occurred when attaching or detaching object
    if prefix:
        # The displayed form was an admin form, so we need to return the admin form back
        # But with errors from the attach/detach form
        try:
            iso = Iso.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Iso.DoesNotExist:
            iso = None

        form_admin = AdminIsoForm(request, iso, request.POST, prefix=prefix)
        # noinspection PyProtectedMember
        form_admin._errors = form._errors
        form = form_admin
        template = 'gui/dc/iso_admin_form.html'
    else:
        template = 'gui/dc/iso_dc_form.html'

    return render(request, template, {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+IsoAdmin
@permission_required(IsoAdminPermission)
@ajax_required
@require_POST
def admin_iso_form(request):
    """
    Ajax page for updating, removing and adding iso images.
    """
    qs = request.GET.copy()

    if request.POST['action'] == 'update':
        try:
            iso = Iso.objects.select_related('owner', 'dc_bound').get(name=request.POST['adm-name'])
        except Iso.DoesNotExist:
            raise Http404
    else:
        iso = None

    form = AdminIsoForm(request, iso, request.POST, prefix='adm')

    if form.is_valid():
        args = (form.cleaned_data['name'],)
        status = form.save(args=args)

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'create' and not form.cleaned_data.get('dc_bound'):
                qs['all'] = 1  # Show all items if adding new item and not attaching
            return redirect('dc_iso_list', query_string=qs)

    return render(request, 'gui/dc/iso_admin_form.html', {'form': form})
