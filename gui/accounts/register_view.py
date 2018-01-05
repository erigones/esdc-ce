from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.db import transaction
from django.views.generic import View
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator

from gui.accounts.forms import UserProfileRegisterForm, RegisterForm
from gui.decorators import logout_required
from gui.accounts.utils import get_initial_data
from api.decorators import setting_required
from api.email import sendmail


class RegisterView(View):
    uform_class = RegisterForm  # Define user form
    upform_class = UserProfileRegisterForm  # Define profile form
    success_redirect = 'registration_done'  # Define name of url where to redirect
    template_name = 'gui/accounts/register.html'  # Define name of template that should generate
    request = None

    @staticmethod
    def _notify_user(request, user, profile):
        """
        Function that notifies user that he has been registered in the system.

        Can be overloaded to send different text in the email, or use different method of notification.
        """
        sendmail(user, 'gui/accounts/register_subject.txt', 'gui/accounts/register_email.txt', extra_context={
            'user': user,
            'profile': profile,
            'token': profile.email_token,
            'uid': urlsafe_base64_encode(str(user.id)),
        }, dc=request.dc)

    # noinspection PyUnusedLocal
    def get(self, request, *args, **kwargs):
        """
        GET method used to generate form, and prepare page before user fills the data in the form and POST it for
        DB storage.
        """
        uform = self.uform_class()
        upform = self.upform_class(initial=get_initial_data(request))

        return render(request, self.template_name, {
            'uform': uform,
            'upform': upform,
            'tos_link': reverse('tos'),
            'failed_registration': False,
        })

    # noinspection PyUnusedLocal
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        POST method that checks the form send by user and store the validated data in the DB.
        """
        uform = self.uform_class(request.POST)
        upform = self.upform_class(request.POST)

        if uform.is_valid() and upform.is_valid():
            user = uform.save(commit=False)
            # Just to be sure - for a never logged-in user this should be True:
            # user.last_login <= user.date_joined
            user.last_login = timezone.datetime(1970, 1, 1, 0, 0, 0, 0, timezone.get_default_timezone())
            # Update username to email for common users
            user.username = user.email.lower()
            # Update user default datacenter
            user.default_dc = request.dc
            # User is not active yet
            user.is_active = False
            # Save user and userprofile
            user.save()
            profile = upform.save(instance=user.userprofile)
            profile.email_token = profile.generate_token(12)
            profile.save()
            # Send email
            self._notify_user(request, user, user.userprofile)

            return redirect(reverse(self.success_redirect))

        return render(request, self.template_name, {
            'uform': uform,
            'upform': upform,
            'tos_link': reverse('tos'),
            'failed_registration': True,
        })

    @method_decorator(logout_required)
    @method_decorator(setting_required('REGISTRATION_ENABLED'))
    def dispatch(self, *args, **kwargs):
        """
        This class is used for decorators that would be used on standard view function
        """
        return super(RegisterView, self).dispatch(*args, **kwargs)
