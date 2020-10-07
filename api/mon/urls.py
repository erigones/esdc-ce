from django.conf.urls import url, include

urlpatterns = [
    url(r'^vm/', include('api.mon.vm.urls')),
    url(r'^node/', include('api.mon.node.urls')),
    url(r'^alert/', include('api.mon.alerting.urls')),
    url(r'^action/', include('api.mon.alerting.action.urls')),
    url(r'^', include('api.mon.base.urls')),
]
