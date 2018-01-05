from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    'api.sms.views',

    url(r'^smsapi/', include('api.sms.smsapi.urls')),
)
