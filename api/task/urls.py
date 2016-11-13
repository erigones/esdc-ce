from django.conf.urls import patterns, url

urlpatterns = patterns(
    'api.task.views',

    url(r'^log/$', 'task_log', name='api_task_log'),
    url(r'^log/report/$', 'task_log_report', name='api_task_log_report'),
    url(r'^(?P<task_id>[A-Za-z0-9-]+)/done/$', 'task_done', name='api_task_done'),
    url(r'^(?P<task_id>[A-Za-z0-9-]+)/status/$', 'task_status', name='api_task_status'),
    url(r'^(?P<task_id>[A-Za-z0-9-]+)/state/$', 'task_status', name='api_task_state'),
    url(r'^(?P<task_id>[A-Za-z0-9-]+)/cancel/$', 'task_cancel', name='api_task_cancel'),
    url(r'^(?P<task_id>[A-Za-z0-9-]+)/$', 'task_details', name='api_task_details'),
    url(r'^$', 'task_list', name='api_task_list'),
)
