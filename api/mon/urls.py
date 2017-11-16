from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    'api.mon.views',

    url(r'^vm/', include('api.mon.vm.urls')),
    url(r'^node/', include('api.mon.node.urls')),
    url(r'^action/', include('api.mon.alerting.action.urls')),
    url(r'^', include('api.mon.base.urls')),

)
