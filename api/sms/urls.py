from django.conf.urls import , url, include

urlpatterns = [
    url(r'^smsapi/', include('api.sms.smsapi.urls')),
]
