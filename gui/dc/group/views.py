from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render, Http404
from django.http import HttpResponse

from gui.models import Role
from gui.decorators import staff_required, ajax_required, admin_required, profile_required
from gui.utils import collect_view_data, reverse, redirect, get_query_string
from gui.dc.group.forms import DcGroupForm, AdminGroupForm


@login_required
@admin_required
@profile_required
def dc_group_list(request):
    """
    Group -> Dc group management.
    """
    user, dc = request.user, request.dc
    groups = Role.objects.order_by('name')
    context = collect_view_data(request, 'dc_group_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff  # No permission for edit (only staff) as other might promote himself
    context['all'] = _all = can_edit and request.GET.get('all', False)
    context['qs'] = qs = get_query_string(request, all=_all,).urlencode()

    if _all:
        context['colspan'] = 5
        context['groups'] = Role.objects.select_related('dc_bound').all()\
                                .prefetch_related('user_set', 'permissions', 'dc_set').order_by('name')
    else:
        context['colspan'] = 4
        context['groups'] = dc.roles.select_related('dc_bound').all()\
                              .prefetch_related('user_set', 'permissions', 'dc_set').order_by('name')

    if can_edit:
        if _all:  # Uses set() because of optimized membership ("in") checking
            context['can_add'] = set(groups.exclude(dc=dc).values_list('pk', flat=True))
        else:  # No need for item list
            context['can_add'] = groups.exclude(dc=dc).count()

        context['url_form_admin'] = reverse('admin_group_form', query_string=qs)
        context['form_admin'] = AdminGroupForm(request, None, prefix='adm', initial={'dc_bound': not is_staff})

        context['form_dc'] = DcGroupForm(request, groups)
        context['url_form_dc'] = reverse('dc_group_form', query_string=qs)

    return render(request, 'gui/dc/group_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_group_form(request):
    """
    Ajax page for attaching and detaching isos.
    """
    if 'adm-name' in request.POST:
        prefix = 'adm'
    else:
        prefix = None

    form = DcGroupForm(request, Role.objects.all().order_by('name'), request.POST, prefix=prefix)

    if form.is_valid():
        status = form.save(args=(form.cleaned_data['name'],))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_group_list', query_string=request.GET)

    # An error occurred when attaching or detaching object
    if prefix:
        # The displayed form was an admin form, so we need to return the admin form back
        # But with errors from the attach/detach form
        try:
            group = Role.objects.select_related('dc_bound').get(name=request.POST['adm-name'])
        except Role.DoesNotExist:
            group = None

        form_admin = AdminGroupForm(request, group, request.POST, prefix=prefix)
        # noinspection PyProtectedMember
        form_admin._errors = form._errors
        form = form_admin
        template = 'gui/dc/group_admin_form.html'
    else:
        template = 'gui/dc/group_dc_form.html'

    return render(request, template, {'form': form})


@login_required
@staff_required
@ajax_required
@require_POST
def admin_group_form(request):
    """
    Ajax page for updating, removing and adding user groups.
    """
    qs = request.GET.copy()

    if request.POST['action'] == 'update':
        try:
            group = Role.objects.select_related('dc_bound').get(name=request.POST['adm-name'])
        except Role.DoesNotExist:
            raise Http404
    else:
        group = None

    form = AdminGroupForm(request, group, request.POST, prefix='adm')

    if form.is_valid():
        args = (form.cleaned_data['name'],)
        status = form.save(args=args)

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'create' and not form.cleaned_data.get('dc_bound'):
                qs['all'] = 1  # Show all items if adding new item and not attaching
            return redirect('dc_group_list', query_string=qs)

    return render(request, 'gui/dc/group_admin_form.html', {'form': form})
