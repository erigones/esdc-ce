from django.dispatch import Signal

task_cleanup_signal = Signal(providing_args=['apiview', 'result', 'task_id', 'status', 'obj'])
