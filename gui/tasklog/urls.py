from django.urls import path

from gui.tasklog.views import index, cached

urlpatterns = [
    path('', index, name='tasklog'),
    path('last/', cached, name='tasklog_cached'),
]
