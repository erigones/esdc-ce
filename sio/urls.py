from django.conf.urls import url

from sio.views import socketio

urlpatterns = [
    url(r'^', socketio, name='socketio'),
]
