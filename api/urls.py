from django.conf.urls import url, include
from django.conf import settings

from api.base.views import api_ping

urlpatterns = [

    url(r'^task/', include('api.task.urls')),
    url(r'^accounts/', include('api.accounts.urls')),
    url(r'^vm/', include('api.vm.urls')),
    url(r'^node/', include('api.node.urls')),
    url(r'^network/', include('api.network.urls')),
    url(r'^image/', include('api.image.urls')),
    url(r'^imagestore/', include('api.imagestore.urls')),
    url(r'^template/', include('api.template.urls')),
    url(r'^iso/', include('api.iso.urls')),
    url(r'^dc/', include('api.dc.urls')),
    url(r'^system/', include('api.system.urls')),
    url(r'ping/$', api_ping, name='api_ping'),
]

if settings.SMS_ENABLED:
    urlpatterns += [url(r'^sms/', include('api.sms.urls'))]

if settings.MON_ZABBIX_ENABLED:
    urlpatterns += [url(r'^mon/', include('api.mon.urls'))]

if settings.DNS_ENABLED:
    urlpatterns += [url(r'^dns/', include('api.dns.urls'))]
