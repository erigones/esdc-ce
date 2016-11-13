from django.shortcuts import render, redirect
from django.db import transaction
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET

from gui.utils import collect_view_data, get_boolean_value
from gui.decorators import ajax_required
from gui.profile.forms import (UserForm, UserProfileForm, EmailActivationProfileForm, PhoneActivationProfileForm,
                               ChangePasswordForm, SSHKeyForm)
from django.shortcuts import get_object_or_404
from gui.models import User
from gui.profile.utils import impersonate_user, impersonate_cancel


@login_required
def index(request):
    """
    User profile page.
    """
    user = request.user
    profile = user.userprofile
    context = collect_view_data(request, 'profile')
    context['user'] = user
    context['profile'] = profile
    context['uform'] = UserForm(request, request.user, init=True)
    context['upform'] = UserProfileForm(request, profile, init=True)
    context['pform'] = ChangePasswordForm(request.user)
    context['sform'] = SSHKeyForm(request, request.user)
    context['ssh_keys'] = request.user.usersshkey_set.all().order_by('id')
    context['email_aform'] = EmailActivationProfileForm(profile.email_token)
    context['phone_aform'] = PhoneActivationProfileForm(profile.phone_token)

    return render(request, 'gui/profile/profile.html', context)


@login_required
@ajax_required
@transaction.atomic
def update(request):
    """
    User profile update.
    """
    user = request.user
    profile = user.userprofile

    if request.method == 'POST':
        uform = UserForm(request, request.user, request.POST)
        upform = UserProfileForm(request, profile, request.POST)
        if uform.is_valid() and upform.is_valid():
            ustatus = uform.save(action='update', args=(request.user.username,))
            upstatus = upform.save(action='update', args=(request.user.username,))

            if (ustatus == 200 and upstatus in (200, 204)) or (upstatus == 200 and ustatus in (200, 204)):
                messages.success(request, _('Your profile was successfully updated'))
                return redirect('profile')
    else:
        uform = UserForm(request, request.user, init=True)
        upform = UserProfileForm(request, profile, init=True)

    return render(request, 'gui/profile/profile_page.html', {
        'user': request.user,
        'profile': profile,
        'uform': uform,
        'upform': upform,
        'ssh_keys': request.user.usersshkey_set.all().order_by('id'),
        'email_aform': EmailActivationProfileForm(profile.email_token),
        'phone_aform': PhoneActivationProfileForm(profile.phone_token),
    })


@login_required
@ajax_required
@require_POST
@transaction.atomic
def activation(request):
    """
    Profile activation page.
    """
    user = request.user
    profile = user.userprofile
    email_aform = None
    phone_aform = None
    status = 200
    email_verified = False

    if not profile.email_verified:
        email_aform = EmailActivationProfileForm(profile.email_token, request.POST)
        if email_aform.is_valid():
            profile.email_token = ''
            profile.email_verified = True
            messages.success(request, _('Your email address was successfully verified'))
            status = 201
            email_verified = True

    if not profile.phone_verified:
        phone_aform = PhoneActivationProfileForm(profile.phone_token, request.POST)
        if phone_aform.is_valid():
            profile.phone_token = ''
            profile.phone_verified = True
            messages.success(request, _('Your phone number was successfully verified'))
            status = 201

    if status == 201:
        profile.save()
        # Update username to email for common users
        if email_verified and not user.is_staff:
            user.username = user.email.lower()
            user.save()
        return redirect('profile')

    return render(request, 'gui/profile/profile_activation_form.html', {
        'user': user,
        'profile': profile,
        'email_aform': email_aform,
        'phone_aform': phone_aform,
    }, status=status)


@login_required
@ajax_required
@require_POST
@transaction.atomic
def password_change(request):
    """
    Ajax page for changing user password.
    """
    status = 200
    pform = ChangePasswordForm(request.user, request.POST)

    if pform.is_valid():
        status = pform.save(request)
        if status == 200:
            messages.success(request, _('Your password was successfully changed'))
            return redirect('profile')

    return render(request, 'gui/profile/profile_password_form.html', {
        'user': request.user,
        'pform': pform,
    }, status=status)


@login_required
@ajax_required
@require_GET
def apikeys(request):
    """
    Ajax page for displaying API keys.
    """
    display = get_boolean_value(request.GET.get('display', False))

    return render(request, 'gui/profile/profile_api_keys_list.html', {
        'user': request.user,
        'display_keys': display
    })


@login_required
@ajax_required
@require_POST
@transaction.atomic
def sshkey(request, action):
    """
    Ajax page for adding or deleting SSH keys.
    """
    if action == 'add':
        sform = SSHKeyForm(request, None, request.POST)
        if sform.is_valid():
            status = sform.save(action='create', args=(request.user.username, sform.cleaned_data['name']))
            if status == 201:
                messages.success(request, _('SSH key was successfully saved'))
                return redirect('profile')

        return render(request, 'gui/profile/profile_sshkey_form.html', {
            'user': request.user,
            'sform': sform
        }, status=200)

    elif action == 'delete':
        res = SSHKeyForm.api_call('delete', None, request, args=(request.user.username, request.POST.get('name')))
        status = res.status_code
        if status == 200:
            messages.success(request, _('SSH key was successfully removed'))
            return redirect('profile')

        return render(request, 'gui/profile/profile_sshkey_list.html', {
            'user': request.user,
            'ssh_keys': request.user.usersshkey_set.all().order_by('id'),
        }, status=status)


@login_required
@require_GET
def start_impersonation(request, username):
    user = get_object_or_404(User, username=username)

    return impersonate_user(request, user.id)


@login_required
@require_GET
def stop_impersonation(request):
    return impersonate_cancel(request)
