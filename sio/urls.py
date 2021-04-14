from django.urls import re_path

from sio.views import socketio

urlpatterns = [
    re_path(r'^.*', socketio, name='socketio'),
]
