from django.conf.urls import url, include
from django.contrib import admin
from django.conf import settings

handler403 = 'core.views.forbidden'
handler404 = 'core.views.page_not_found'
handler500 = 'core.views.server_error'

urlpatterns = [
    # api urls - WARNING: Do NOT change this URL
    url(r'^api/', include('api.urls')),
    # gui urls
    url(r'^', include('gui.urls')),
    # sio urls
    url(r'^socket\.io/', include('sio.urls')),
]

if settings.THIRD_PARTY_APPS_ENABLED:
    # Allow to overload ESDC CE URLs with third party app custom functionality.
    for app in settings.THIRD_PARTY_APPS:
        urlpatterns = [url(r'', include(app + '.urls')),] + urlpatterns

if settings.DEBUG:
    urlpatterns = [
        # url(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT,
        #                                                          'show_indexes': True}),
        url(r'', include('django.contrib.staticfiles.urls')),
        # Django Admin URLs
        url(r'^' + settings.ADMIN_URL, include(admin.site.urls)),
    ] + urlpatterns
