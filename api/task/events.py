from api.event import Event


class TaskCreatedEvent(Event):
    """
    A `task-created` event that replaces the celery's `task-sent` event.
    Sent by TaskResponse for every PENDING/STARTED task.
    """
    _type_ = _name_ = 'task-created'
