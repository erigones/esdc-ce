from django.urls import path

from sio.views import socketio

urlpatterns = [
    path('', socketio, name='socketio'),
]
