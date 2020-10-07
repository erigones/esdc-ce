from django.conf.urls import url
from django.views.generic import RedirectView

from gui.system.views import overview, settings, maintenance, system_update_form, system_node_update_form

urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/system/overview/', permanent=False)),
    url(r'^overview/$', overview, name='system_overview'),
    url(r'^settings/$', settings, name='system_settings'),
    url(r'^maintenance/$', maintenance, name='system_maintenance'),
    url(r'^maintenance/update/form/$', system_update_form, name='system_update_form'),
    url(r'^maintenance/node-update/form/$', system_node_update_form, name='system_node_update_form'),
]
