from django.urls import path, re_path

from sio.views import socketio

urlpatterns = [
    #path('', socketio, name='socketio'),
    re_path(r'^.*', socketio, name='socketio'),
]
