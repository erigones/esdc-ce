from django.conf.urls import patterns, url

urlpatterns = patterns(
    'sio.views',

    url(r'^', 'socketio', name='socketio'),
)
