from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView
from django.conf import settings

js_info_dict = {
    'packages': ('gui', 'api'),
}

urlpatterns = patterns(
    'gui.views',

    # index redirect to Dashboard
    url(r'^$', RedirectView.as_view(url='servers/', permanent=False)),
    # redirect to user guide (this URL is used in ErigonOS installer)
    url(r'^doc/$', RedirectView.as_view(url='/docs/user-guide/', permanent=False)),
    # Translation for server gsio javascript file
    url(r'^jsi18n/$', 'cached_javascript_catalog', js_info_dict, name='javascript_catalog'),
    # Registration pages
    url(r'^accounts/', include('gui.accounts.urls')),
    # Profile pages
    url(r'^accounts/profile/', include('gui.profile.urls')),
    # System pages
    url(r'^dashboard/$', RedirectView.as_view(url='/system/overview/', permanent=False)),
    url(r'^system/', include('gui.system.urls')),
    # Datacenter pages
    url(r'^dc/', include('gui.dc.urls')),
    # Node pages
    url(r'^node/', include('gui.node.urls')),
    # Documentation pages
    url(r'^docs/', include('gui.docs.urls')),
    # Server pages
    url(r'^servers/', include('gui.vm.urls')),
    # Monitoring pages
    url(r'^monitoring/', include('gui.mon.urls')),
    # Task log
    url(r'^tasklog/', include('gui.tasklog.urls')),
)

# Support pages
if settings.SUPPORT_ENABLED:
    urlpatterns += patterns('', url(r'^support/', include('gui.support.urls')))
