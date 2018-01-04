from os import path

from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.utils.translation import LANGUAGE_SESSION_KEY, check_for_language, ugettext_lazy as _
from django.utils.http import is_safe_url, urlsafe_base64_decode
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_reset, password_reset_confirm, logout_then_login, login as contrib_login
from logging import getLogger
from functools import partial

from gui.vm.guacamole import GuacamoleAuth
from gui.models import User
from gui.accounts.forms import LoginForm, ForgotForm, SMSSendPasswordResetForm, PasswordResetForm
from gui.accounts.utils import get_client_ip, clear_attempts_cache
from gui.decorators import logout_required
from api.decorators import setting_required
from api.email import sendmail
from api.sms.views import internal_send as send_sms
from api.sms.exceptions import SMSError
from vms.models import DefaultDc

logger = getLogger(__name__)
auth_logger = getLogger('gui.auth')


# noinspection PyShadowingBuiltins
def setlang(request):
    """
    Sets a user's language preference and redirects to a given URL or, by default, back to the previous page.
    """
    next = request.GET.get('next', None)
    if not is_safe_url(url=next, host=request.get_host()):
        next = request.META.get('HTTP_REFERER')
        if not is_safe_url(url=next, host=request.get_host()):
            next = '/'
    response = redirect(next)

    lang_code = request.GET.get('language', None)
    if lang_code and check_for_language(lang_code):
        if hasattr(request, 'session'):
            request.session[LANGUAGE_SESSION_KEY] = lang_code
        else:
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code,
                                max_age=settings.LANGUAGE_COOKIE_AGE,
                                path=settings.LANGUAGE_COOKIE_PATH,
                                domain=settings.LANGUAGE_COOKIE_DOMAIN)

    return response


@logout_required
@setting_required('REGISTRATION_ENABLED')
def registration_done(request):
    """
    Confirmation page after successful registration.
    """
    dc_settings = request.dc.settings
    dc1_settings = DefaultDc().settings
    text_blocks = [
        _('Thank you for registering at %s.') % dc_settings.SITE_NAME,
        _('You should receive an email shortly. Please click on the link in the email to activate your account.'),
        _('If you don\'t receive an email, please check your spam folder.'),
    ]

    if dc1_settings.SMS_REGISTRATION_ENABLED:
        text_blocks.append(_('Once your account is active, you will receive a text message (SMS) with your password.'))

    return render(request, 'gui/note.html', {
        'header': _('Registration almost complete!'),
        'blocks': text_blocks,
    })


def send_post_register_email(request, user):
    # Send optional email after successful registration (issue #261)
    template_path = path.join(settings.PROJECT_DIR, 'gui', 'templates')
    subject = 'gui/accounts/post_register_subject.txt'
    subject_path = path.join(template_path, subject)
    body_file_prefix = 'gui/accounts/post_register_email'
    body = None

    if path.exists(subject_path) and path.exists(path.join(template_path, body_file_prefix + '.html')):
        body = body_file_prefix + '.html'
    elif path.exists(subject_path) and path.exists(path.join(template_path, body_file_prefix + '.txt')):
        body = body_file_prefix + '.txt'

    if body:
        sendmail(user, subject, body, dc=request.dc)
    else:
        logger.info('Post registration email subject template: "%s" or body template: "%s" does not exists.' %
                    (subject_path, path.join(template_path, body_file_prefix + '.[html|txt]')))


def send_registration_sms(request, profile, password):
    msg = _('Welcome to %(site_name)s, your new password is: %(password)s') % {
        'site_name': request.dc.settings.SITE_NAME,
        'password': password
    }
    try:
        send_sms(profile.phone, msg)
    except SMSError:
        return False
    else:
        return True


@logout_required
@setting_required('REGISTRATION_ENABLED')
@never_cache
def registration_check(request, uidb64=None, token=None):
    """
    Email verification page, generating password and sending it to user.
    """
    assert uidb64 is not None and token is not None
    success = False
    token_verified = False
    dc_settings = request.dc.settings
    dc1_settings = DefaultDc().settings
    sms_registration = dc1_settings.SMS_REGISTRATION_ENABLED

    try:
        user = User.objects.get(id=urlsafe_base64_decode(uidb64))
        profile = user.userprofile
    except (ValueError, OverflowError, User.DoesNotExist):
        user = None
        profile = None

    if profile and user.last_login <= user.date_joined and profile.email_token == token:
        token_verified = True
        # Set default user type
        profile.usertype = dc1_settings.PROFILE_USERTYPE_DEFAULT
        # Email address is verified
        profile.email_token = ''
        profile.email_verified = True
        # This may look strange - setting the phone_verified before the user logs in. It is not :) Actually we have
        # the last_login field, which should be set to None at this point. So we know that the user never logged in and
        # after the user logs in we would set phone_verified to True anyway.
        if sms_registration:
            profile.phone_verified = True
        profile.save()

        if sms_registration:
            # Generate new password
            password = User.objects.make_random_password(length=7)
            user.set_password(password)
        else:
            password = None

        user.is_active = True
        user.save()

        if password:
            # Send new password to user via SMS
            success = send_registration_sms(request, profile, password)
        else:
            success = True

        try:
            send_post_register_email(request, user)
        except Exception as exc:
            logger.exception(exc)

    return render(request, 'gui/accounts/register_check.html', {
        'user': user,
        'profile': profile,
        'sms_registration': sms_registration,
        'success': success,
        'token_verified': token_verified,
        'site_name': dc_settings.SITE_NAME,
        'support_email': dc_settings.SUPPORT_EMAIL,
    })


@logout_required
@setting_required('REGISTRATION_ENABLED')
def forgot_passwd(request):
    """
    User password reset page.
    """
    dc_settings = request.dc.settings

    return password_reset(
        request,
        template_name='gui/accounts/forgot.html',
        email_template_name='gui/accounts/forgot_email.txt',
        subject_template_name='gui/accounts/forgot_subject.txt',
        password_reset_form=partial(ForgotForm, request),
        post_reset_redirect=reverse('forgot_done'),
        from_email=dc_settings.DEFAULT_FROM_EMAIL,
        current_app='gui',
        extra_context={
            'e_site_name': dc_settings.SITE_NAME,
            'e_site_link': dc_settings.SITE_LINK,
        })


@logout_required
@setting_required('REGISTRATION_ENABLED')
def forgot_passwd_done(request):
    """
    Confirmation page after successful password reset request.
    """
    return render(request, 'gui/note.html', {
        'header': _('Password reset instructions!'),
        'blocks': (
            _('We\'ve emailed you instructions for setting your password. You should be receiving them shortly.'),
            _('If you don\'t receive an email, please make sure you\'ve entered the address you registered with, and '
              'check your spam folder.'),
        )
    })


@logout_required
@setting_required('REGISTRATION_ENABLED')
@never_cache
def forgot_passwd_check(request, uidb64=None, token=None):
    """
    Page that checks the hash in a password reset link, generates a new password which is send via SMS to the user.
    """
    assert uidb64 is not None and token is not None
    dc1_settings = DefaultDc().settings
    sms_registration = dc1_settings.SMS_REGISTRATION_ENABLED

    if sms_registration:
        set_password_form = SMSSendPasswordResetForm
    else:
        set_password_form = PasswordResetForm

    if request.method == 'POST':
        try:
            user = User.objects.get(id=urlsafe_base64_decode(uidb64))
            profile = user.userprofile
        except (ValueError, OverflowError, User.DoesNotExist):
            profile = None

        if profile and profile.email_token == token:
            # Email address is verified, we cant compare to token as register token is different to reset one.
            profile.email_token = ''
            profile.email_verified = True
            # This may look strange - setting the phone_verified before the user logs in. It is not :) We are sending
            # new password to phone number in profile, after the user logs in we would set phone_verified to True anyway
            if sms_registration:
                profile.phone_verified = True
            profile.save()

    return password_reset_confirm(
        request,
        uidb64=uidb64,
        token=token,
        template_name='gui/accounts/forgot_check.html',
        set_password_form=set_password_form,
        post_reset_redirect=reverse('forgot_check_done'),
        current_app='gui',
        extra_context={
            'sms_registration': sms_registration,
        }
    )


@logout_required
@setting_required('REGISTRATION_ENABLED')
def forgot_passwd_check_done(request):
    """
    Confirmation page after successful password reset.
    """
    dc1_settings = DefaultDc().settings

    if dc1_settings.SMS_REGISTRATION_ENABLED:
        text_blocks = (_('Your password has been reset and send to your phone number via text message (SMS).'),)
    else:
        text_blocks = ()

    return render(request, 'gui/note.html', {
        'header': _('Password reset!'),
        'blocks': text_blocks,
        'links': ({'label': 'You may go ahead and log in now.', 'url': reverse('login')},),
    })


@logout_required
def login(request):
    """
    Log users in the system and re-direct them to dashboard or show proper error message when failed.
    """
    response = contrib_login(request, 'gui/accounts/login.html', authentication_form=partial(LoginForm, request))

    # Setup i18n settings into session
    if request.method == 'POST':
        user = request.user
        if user.is_authenticated():
            auth_logger.info('User %s successfully logged in from %s (%s)', user, get_client_ip(request),
                             request.META.get('HTTP_USER_AGENT', ''))
            user.userprofile.activate_locale(request)
            clear_attempts_cache(request, user.username)
        else:
            auth_logger.warning('User %s login failed from %s (%s)', request.POST.get('username', None),
                                get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))

    return response


@login_required
def logout(request):
    """
    Log users out (destroy all sessions) and re-direct them to the main page.
    """
    # Save profile and user object
    user = request.user
    profile = request.user.userprofile
    # Create guacamole object attached to request.user.username and with current guacamole password
    g = GuacamoleAuth(request)
    # Do a guacamole logout
    gcookie = g.logout()
    # We can then remove the cached configuration
    g.del_auth()
    # Get the response object
    response = logout_then_login(request)
    # Remove the guacamole cookie from response object
    response.delete_cookie(**gcookie['cookie'])
    # Setup i18n settings of the logged in user into session of an anonymous user
    profile.activate_locale(request)
    # Get auth logger and log the logout :)
    auth_logger.info('User %s successfully logged out from %s (%s)',
                     user, get_client_ip(request), request.META.get('HTTP_USER_AGENT', ''))

    # Bye bye
    return response
