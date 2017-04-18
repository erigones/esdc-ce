from django.conf.urls import patterns, url, include

from .base import views

urlpatterns = patterns(
    'api.mon.views',

    url(r'^vm/', include('api.mon.vm.urls')),
    url(r'^node/', include('api.mon.node.urls')),
    url(r'^template/', views.mon_template_list),
)
