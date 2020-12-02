from django.conf.urls import url
from django.urls import path, re_path
from django.views.generic import RedirectView
from django.conf import settings
from gui.accounts.register_view import RegisterView
from gui.accounts.views import setlang, logout
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, LoginView


urlpatterns = [
    path('setlang/', setlang, name='setlang'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout, name='logout'),
]


# if settings.REGISTRATION_ENABLED:
#     from gui.accounts.views import forgot_passwd, registration_done, forgot_passwd_check, forgot_passwd_done, \
#         forgot_passwd_check_done
#
#     urlpatterns += [
#         path('tos/', RedirectView.as_view(url=settings.TOS_LINK, permanent=False), name='tos'),
#         path('register/', RegisterView.as_view(), name='registration'),
#         path('register/done/', registration_done, name='registration_done'),
#         re_path(r'^register/verify/(?P<uidb64>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,24})/$', 'registration_check',
#             name='registration_check'),
#         path('forgot_password/', forgot_passwd, name='forgot'),
#         path('forgot_password/done/', forgot_passwd_done, name='forgot_done'),
#         path('forgot_password/reset/done/', forgot_passwd_check_done, name='forgot_check_done'),
#         re_path(r'^forgot_password/reset/(?P<uidb64>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
#             forgot_passwd_check, name='forgot_check')
#     ]
