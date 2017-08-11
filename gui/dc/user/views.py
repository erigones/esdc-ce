from django.db.models import Q
from django.db import transaction
from django.utils.translation import ugettext_lazy as _
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render
from django.http import HttpResponse

from api.accounts.user.utils import ExcludeInternalUsers
from gui.models.permission import UserAdminPermission
from gui.models.user import User
from gui.decorators import ajax_required, staff_required, admin_required, profile_required, permission_required
from gui.utils import get_boolean_value, collect_view_data, reverse, redirect, get_query_string
from gui.dc.user.utils import get_edited_user
from gui.dc.user.forms import AdminUserForm, AdminUserModalForm, AdminUserProfileForm, AdminChangePasswordForm
from gui.profile.forms import SSHKeyForm


class AllIn(set):
    """Universal set - match everything"""
    def __contains__(self, item):
        return True


@login_required
@admin_required
@profile_required
def dc_user_list(request):
    """
    User -> Dc group management.
    """
    user, dc = request.user, request.dc
    users = User.objects.order_by('username').filter(ExcludeInternalUsers)
    context = collect_view_data(request, 'dc_user_list')
    context['is_staff'] = is_staff = user.is_staff
    context['can_edit'] = can_edit = is_staff or user.has_permission(request, UserAdminPermission.name)
    context['all'] = _all = can_edit and request.GET.get('all', False)
    context['active'] = _active = not (can_edit and request.GET.get('inactive', False))
    context['qs'] = qs = get_query_string(request, all=_all, inactive=_active).urlencode()

    if _all or dc.access == dc.PUBLIC:
        if _all:
            pr = ('roles', 'roles__dc_set')
        else:
            pr = ('roles',)

        context['users'] = users.select_related('dc_bound').filter(is_active=_active).prefetch_related(*pr)

        if dc.access == dc.PUBLIC:
            context['dc_users'] = AllIn()
        else:
            # Uses set() because of optimized membership ("in") checking
            context['dc_users'] = set(users.filter((Q(id=dc.owner.id) | Q(roles__in=dc.roles.all())))
                                           .values_list('pk', flat=True))
    else:
        context['users'] = users.select_related('dc_bound')\
                                .filter(is_active=_active)\
                                .filter(Q(id=dc.owner.id) | Q(roles__in=dc.roles.all()) | Q(dc_bound=dc))\
                                .prefetch_related('roles').distinct()

    if can_edit:
        context['url_form_admin'] = reverse('dc_user_modal_form', query_string=qs)
        context['form_admin'] = AdminUserModalForm(request, None, prefix='adm', initial={'dc_bound': not is_staff,
                                                                                         'is_active': True})

    return render(request, 'gui/dc/user_list.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+UserAdmin
@permission_required(UserAdminPermission)
@ajax_required
@require_POST
def dc_user_modal_form(request):
    """
    Ajax page for updating, removing and adding user.
    """
    qs = request.GET.copy()

    if request.POST['action'] == 'update':
        user = get_edited_user(request, request.POST['adm-username'])
    else:
        user = None

    form = AdminUserModalForm(request, user, request.POST, prefix='adm')

    if form.is_valid():
        args = (form.cleaned_data['username'],)
        status = form.save(args=args)

        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'create':
                messages.success(request, _('User was successfully created'))
                return redirect('dc_user_profile', username=form.cleaned_data['username'])
            else:
                messages.success(request, _('User profile was successfully updated'))
                user = user.__class__.objects.get(pk=user.pk)  # Reload user object from DB (modified in API)
                # You can modify yourself and lose access to /dc - Issue #108
                if request.user == user and not user.is_admin(dc=request.dc):
                    redirect_to = '/'
                else:
                    redirect_to = 'dc_user_list'

                return redirect(redirect_to, query_string=qs)

    return render(request, 'gui/dc/user_dc_form.html', {'form': form})


@login_required
@admin_required  # SuperAdmin or DCAdmin+UserAdmin
@permission_required(UserAdminPermission)
@profile_required
def dc_user_profile(request, username):
    """
    User Profile management.
    """
    user = get_edited_user(request, username, sr=('dc_bound', 'userprofile'))
    profile = user.userprofile
    context = collect_view_data(request, 'dc_user_list')
    context['uform'] = AdminUserForm(request, user, init=True)
    context['upform'] = AdminUserProfileForm(request, profile, init=True)
    context['pform'] = AdminChangePasswordForm(user)
    context['sform'] = SSHKeyForm(request, user)
    context['user'] = user
    context['profile'] = profile
    context['ssh_keys'] = user.usersshkey_set.all().order_by('id')
    if not request.user.is_staff:
        context['disabled_api_key'] = True

    return render(request, 'gui/dc/profile/user_profile.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+UserAdmin
@permission_required(UserAdminPermission)
@ajax_required
@require_POST
def dc_user_profile_form(request, username):
    """
    Ajax page for updating user profile.
    """
    user = get_edited_user(request, username, sr=('dc_bound', 'userprofile'))
    profile = user.userprofile

    if request.POST['action'] == 'update':
        uform = AdminUserForm(request, user, request.POST)
        upform = AdminUserProfileForm(request, profile, request.POST)

        if uform.is_valid() and upform.is_valid():  # The real validation is not happening here but below
            args = (uform.cleaned_data['username'],)
            # The validation happens in these two forms and they inform about the result which we process.
            # However, if upform save fails, uform is saved already and we cannot do anything about that.
            # FIXME bad design here and in gui.profile.views.update
            ustatus = uform.save(action='update', args=args)
            upstatus = upform.save(action='update', args=args)

            if (ustatus == 200 and upstatus in (200, 204)) or (upstatus == 200 and ustatus in (200, 204)):
                messages.success(request, _('User profile was successfully updated'))
                user = user.__class__.objects.get(pk=user.pk)  # Reload user object from DB (modified in API)
                # You can modify yourself and lose access to /dc - Issue #108
                if request.user == user and not user.is_admin(dc=request.dc):
                    redirect_to = '/'
                else:
                    redirect_to = 'dc_user_list'

                return redirect(redirect_to)

    else:
        uform = AdminUserForm(request, user, init=True)
        upform = AdminUserProfileForm(request, profile, init=True)

    context = {
        'uform': uform,
        'upform': upform,
        'user': user,
        'profile': profile,
        'ssh_keys': user.usersshkey_set.all().order_by('id'),
    }

    if not request.user.is_staff:
        context['disabled_api_key'] = True

    return render(request, 'gui/dc/profile/profile_page.html', context)


@login_required
@admin_required  # SuperAdmin or DCAdmin+UserAdmin
@permission_required(UserAdminPermission)
@ajax_required
@require_POST
@transaction.atomic
def dc_user_profile_password_modal_form(request, username):
    """
    Ajax page for changing user password.
    """
    user = get_edited_user(request, username)
    status = 200
    pform = AdminChangePasswordForm(user, request.POST)

    if pform.is_valid():
        status = pform.save(request)
        if status == 200:
            messages.success(request, _('User password was successfully changed'))
            return redirect('dc_user_profile', user.username)

    return render(request, 'gui/dc/profile/profile_password_form.html', {
        'user': user,
        'pform': pform,
    }, status=status)


@login_required
@staff_required  # SuperAdmin
@ajax_required
@require_GET
def dc_user_profile_apikeys(request, username):
    """
    Ajax page for displaying API keys.
    """
    user = get_edited_user(request, username)
    display = get_boolean_value(request.GET.get('display', False))

    return render(request, 'gui/profile/profile_api_keys_list.html', {
        'user': user,
        'display_keys': display
    })


@login_required
@admin_required  # SuperAdmin or DCAdmin+UserAdmin
@permission_required(UserAdminPermission)
@ajax_required
@require_POST
@transaction.atomic
def dc_user_profile_sshkey_modal_form(request, username, action):
    """
    Ajax page for adding or deleting SSH keys.
    """
    user = get_edited_user(request, username)

    if action == 'add':
        sform = SSHKeyForm(request, None, request.POST)
        if sform.is_valid():
            status = sform.save(action='create', args=(user.username, sform.cleaned_data['name']))
            if status == 201:
                messages.success(request, _('SSH key was successfully saved'))
                return redirect('dc_user_profile', user.username)

        return render(request, 'gui/profile/profile_sshkey_form.html', {
            'user': user,
            'sform': sform
        }, status=200)

    elif action == 'delete':
        res = SSHKeyForm.api_call('delete', None, request, args=(user.username, request.POST.get('name')))
        status = res.status_code
        if status == 200:
            messages.success(request, _('SSH key was successfully removed'))
            return redirect('dc_user_profile', user.username)

        return render(request, 'gui/profile/profile_sshkey_list.html', {
            'user': user,
            'ssh_keys': user.usersshkey_set.all().order_by('id')
        }, status=status)
