from django.urls import path
from django.views.generic import RedirectView

from gui.system.views import overview, settings, maintenance, system_update_form, system_node_update_form

urlpatterns = [
    path('', RedirectView.as_view(url='/system/overview/', permanent=False)),
    path('overview/', overview, name='system_overview'),
    path('settings/', settings, name='system_settings'),
    path('maintenance/', maintenance, name='system_maintenance'),
    path('maintenance/update/form/', system_update_form, name='system_update_form'),
    path('maintenance/node-update/form/', system_node_update_form, name='system_node_update_form'),
]
