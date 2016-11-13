from django.conf.urls import patterns, url, include

urlpatterns = patterns(
    'api.mon.views',

    url(r'^vm/', include('api.mon.vm.urls')),
    url(r'^node/', include('api.mon.node.urls')),
)
