from logging import getLogger
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.db import transaction
from django.views.generic import View
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.utils.decorators import method_decorator

from gui.accounts.forms import RegisterForm, UserProfileRegisterForm
from gui.decorators import logout_required
from gui.accounts.utils import get_initial_data
from api.decorators import setting_required
from api.email import sendmail

logger = getLogger(__name__)


class RegisterView(View):
    uform_class = RegisterForm  # Define user form
    upform_class = UserProfileRegisterForm  # Define profile form
    store_form = True  # store user, (profile have to be saved in)
    success_redirect = 'registration_done'  # Define name of url where to redirect
    template_name = 'gui/accounts/register.html'  # Define name of template that should generate
    notify_user = True  # call notification function (send email)
    request = None

    @method_decorator(logout_required)
    @method_decorator(setting_required('REGISTRATION_ENABLED'))
    def dispatch(self, *args, **kwargs):
        """
        This class is used for decorators that would be used on standard view function
        """
        return super(RegisterView, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        GET method used to generate form, and prepare page before user fills the data in the form and POST it for
        DB storage.
        """
        self.request = request
        self._pre_view_callback(*args, **kwargs)
        uform = self.uform_class()
        upform = self.upform_class(initial=get_initial_data(request))
        context = {
            'uform': uform,
            'upform': upform,
            'failed_registration': False,
        }
        context = self._update_context(context, *args, **kwargs)

        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        POST method that checks the form send by user and store the validated data in the DB.
        """
        self.request = request
        uform = self.uform_class(request.POST)
        upform = self.upform_class(request.POST)

        if uform.is_valid() and upform.is_valid():
            user = uform.save(commit=False)

            user, upform = self._pre_save_callback(user, upform, *args, **kwargs)

            if self.store_form:
                user.save()

            self._post_save_callback(user, upform, *args, **kwargs)

            if self.notify_user:
                self._notify_user(user, user.userprofile)

            if self.success_redirect:
                return redirect(reverse(self.success_redirect))

        context = {
            'uform': uform,
            'upform': upform,
            'failed_registration': True,
        }
        context = self._update_context(context, *args, **kwargs)

        return render(request, self.template_name, context)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _update_context(self, context, *args, **kwargs):
        """
        Pass additional variables to the template. Useful for overloaded classes if the need something special in
        template, when rendering the form (either the initial one or when form has validation error).
        """
        context['tos_link'] = reverse('tos')
        return context

    # noinspection PyUnusedLocal
    def _pre_save_callback(self, user, upform, *args, **kwargs):
        """
        Stuff that needs to be done pre-saving the user object.
        """
        # Just to be sure - for a never logged-in user this should be True:
        # user.last_login <= user.date_joined
        user.last_login = timezone.datetime(1970, 1, 1, 0, 0, 0, 0, timezone.get_default_timezone())
        # Update username to email for common users
        user.username = user.email.lower()
        # Update user default datacenter
        user.default_dc = self.request.dc

        return user, upform

    # noinspection PyUnusedLocal
    def _post_save_callback(self, user, upform, *args, **kwargs):
        """
        Stuff that needs to be done after post-saving the user object.
        """
        if self.store_form:
            profile = upform.save(instance=user.userprofile)
            profile.email_token = profile.generate_token(12)
            profile.save()

    # noinspection PyMethodMayBeStatic
    def _pre_view_callback(self, *args, **kwargs):
        """
        Function called before rendering the GET form, useful for overloaded called if the need to check conditions
        if user is able to register (eg. check params in URL, etc.)
        """
        pass

    def _notify_user(self, user, profile):
        """
        Function that notifies user that he has been registered in the system.

        Can be overloaded to send different text in the email, or use different method of notification.
        Function can be suppressed not to be called at all by setting self.notify_user = False in child __init__
        """
        sendmail(user, 'gui/accounts/register_subject.txt', 'gui/accounts/register_email.txt', extra_context={
            'user': user,
            'profile': profile,
            'token': profile.email_token,
            'uid': urlsafe_base64_encode(str(user.id)),
        }, dc=self.request.dc)
