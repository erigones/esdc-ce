from django.urls import path, include
from django.conf import settings

from api.base.views import api_ping

urlpatterns = [

    path('task/', include('api.task.urls')),
    path('accounts/', include('api.accounts.urls')),
    path('vm/', include('api.vm.urls')),
    path('node/', include('api.node.urls')),
    path('network/', include('api.network.urls')),
    path('image/', include('api.image.urls')),
    path('imagestore/', include('api.imagestore.urls')),
    path('template/', include('api.template.urls')),
    path('iso/', include('api.iso.urls')),
    path('dc/', include('api.dc.urls')),
    path('system/', include('api.system.urls')),
    path('ping/', api_ping, name='api_ping'),
]

if settings.SMS_ENABLED:
    urlpatterns += [path('sms/', include('api.sms.urls'))]

if settings.MON_ZABBIX_ENABLED:
    urlpatterns += [path('mon/', include('api.mon.urls'))]

if settings.DNS_ENABLED:
    urlpatterns += [path('dns/', include('api.dns.urls'))]
