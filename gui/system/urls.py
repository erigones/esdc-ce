from django.conf.urls import patterns, url
from django.views.generic import RedirectView

urlpatterns = patterns(
    'gui.system.views',

    url(r'^$', RedirectView.as_view(url='/system/overview/', permanent=False)),
    url(r'^overview/$', 'overview', name='system_overview'),
    url(r'^settings/$', 'settings', name='system_settings'),
    url(r'^maintenance/$', 'maintenance', name='system_maintenance'),
)
