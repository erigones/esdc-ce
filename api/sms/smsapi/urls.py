from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.sms.smsapi.views',

    url(r'callback/$', 'callback', name='sms_smsapi_callback'),
)
