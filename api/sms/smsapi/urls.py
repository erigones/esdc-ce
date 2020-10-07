from django.conf.urls import url

from api.sms.smsapi.views import callback

urlpatterns = [
    url(r'callback/$', callback, name='sms_smsapi_callback'),
]
