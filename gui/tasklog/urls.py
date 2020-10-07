from django.conf.urls import url

from gui.tasklog.views import index, cached

urlpatterns = [
    url(r'^$', index, name='tasklog'),
    url(r'^last/$', cached, name='tasklog_cached'),
]
