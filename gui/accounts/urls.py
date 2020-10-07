from django.conf.urls import url
from django.views.generic import RedirectView
from django.conf import settings
from gui.accounts.register_view import RegisterView
from gui.accounts.views import setlang, logout, login

urlpatterns = [
    url(r'^setlang/$', setlang, name='setlang'),
    url(r'^login/$', login, name='login'),
    url(r'^logout/$', logout, name='logout'),
]


if settings.REGISTRATION_ENABLED:
    from gui.accounts.views import forgot_passwd, registration_done, forgot_passwd_check, forgot_passwd_done, \
        forgot_passwd_check_done

    urlpatterns += [
        url(r'^tos/$', RedirectView.as_view(url=settings.TOS_LINK, permanent=False), name='tos'),
        url(r'^register/$', RegisterView.as_view(), name='registration'),
        url(r'^register/done/$', registration_done, name='registration_done'),
        url(r'^register/verify/(?P<uidb64>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,24})/$', 'registration_check',
            name='registration_check'),
        url(r'^forgot_password/$', forgot_passwd, name='forgot'),
        url(r'^forgot_password/done/$', forgot_passwd_done, name='forgot_done'),
        url(r'^forgot_password/reset/done/$', forgot_passwd_check_done, name='forgot_check_done'),
        url(r'^forgot_password/reset/(?P<uidb64>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
            forgot_passwd_check, name='forgot_check')
    ]
