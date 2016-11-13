from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    'api.sms.views',

    url(r'^send/$', 'send', name='sms_send'),
    url(r'^smsapi/', include('api.sms.smsapi.urls')),
)
