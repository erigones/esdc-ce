from django.urls import path, include

urlpatterns = [
    path('smsapi/', include('api.sms.smsapi.urls')),
]
