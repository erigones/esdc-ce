from django.urls import path, re_path

from api.task.views import task_log, task_log_stats, task_done, task_status, task_cancel, task_details, task_list

urlpatterns = [
    path('log/', task_log, name='api_task_log'),
    path('log/stats/', task_log_stats, name='api_task_log_stats'),
    re_path(r'^(?P<task_id>[A-Za-z0-9-]+)/done/$', task_done, name='api_task_done'),
    re_path(r'^(?P<task_id>[A-Za-z0-9-]+)/status/$', task_status, name='api_task_status'),
    re_path(r'^(?P<task_id>[A-Za-z0-9-]+)/state/$', task_status, name='api_task_state'),
    re_path(r'^(?P<task_id>[A-Za-z0-9-]+)/cancel/$', task_cancel, name='api_task_cancel'),
    re_path(r'^(?P<task_id>[A-Za-z0-9-]+)/$', task_details, name='api_task_details'),
    path('', task_list, name='api_task_list'),
]
