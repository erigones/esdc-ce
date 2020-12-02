from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings

from gui.views import cached_javascript_catalog

js_info_dict = {
    'packages': ('gui', 'api'),
}

urlpatterns = [
    # index redirect to Dashboard
    path('', RedirectView.as_view(url='servers/', permanent=False)),
    # redirect to user guide (this pathp is used in ErigonOS installer)
    path('doc/', RedirectView.as_view(url='/docs/user-guide/', permanent=False)),
    # Translation for server gsio javascript file
    path('jsi18n/', cached_javascript_catalog, js_info_dict, name='javascript_catalog'),
    # Registration pages
    path('accounts/', include('gui.accounts.urls')),
    # Profile pages
    path('accounts/profile/', include('gui.profile.urls')),
    # System pages
    path('dashboard/', RedirectView.as_view(url='/system/overview/', permanent=False)),
    path('system/', include('gui.system.urls')),
    # Datacenter pages
    path('dc/', include('gui.dc.urls')),
    # Node pages
    path('node/', include('gui.node.urls')),
    # Documentation pages
    path('docs/', include('gui.docs.urls')),
    # Server pages
    path('servers/', include('gui.vm.urls')),
    # Monitoring pages
    path('monitoring/', include('gui.mon.urls')),
    # Task log
    path('tasklog/', include('gui.tasklog.urls')),
]

# Support pages
if settings.SUPPORT_ENABLED:
    urlpatterns += [
        path('support/', include('gui.support.urls'))
    ]
