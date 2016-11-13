from django.conf.urls import patterns, url

urlpatterns = patterns(
    'gui.tasklog.views',

    url(r'^$', 'index', name='tasklog'),
    url(r'^last/$', 'cached', name='tasklog_cached'),
)
