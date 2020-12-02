from django.urls import path

from api.sms.smsapi.views import callback

urlpatterns = [
    path('callback/$', callback, name='sms_smsapi_callback'),
]
