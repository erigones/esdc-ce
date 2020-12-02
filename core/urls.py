from django.urls import path, include
from django.contrib import admin
from django.conf import settings

handler403 = 'core.views.forbidden'
handler404 = 'core.views.page_not_found'
handler500 = 'core.views.server_error'

urlpatterns = [
    # api urls - WARNING: Do NOT change this URL
    path('api/', include('api.urls')),
    # gui urls
    path('', include('gui.urls')),
    # sio urls
    path('socket.io/', include('sio.urls')),
]

if settings.THIRD_PARTY_APPS_ENABLED:
    # Allow to overload ESDC CE URLs with third party app custom functionality.
    for app in settings.THIRD_PARTY_APPS:
        urlpatterns = [path('', include(app + '.urls')),] + urlpatterns

if settings.DEBUG:
    urlpatterns = [
        # re_path(r'^media/(?P<path>.*)$', django.views.static.serve, {'document_root': settings.MEDIA_ROOT,
        #                                                              'show_indexes': True}),
        path('', include('django.contrib.staticfiles.urls')),
        # Django Admin URLs
        path('' + settings.ADMIN_URL, admin.site.urls),
    ] + urlpatterns
