class TaskException(Exception):
    """
    Like classic Exception, but we keep the task result, which gets spoiled by celery cache result backend.

    The kwargs parameter is used for passing custom metadata.
    """
    obj = None

    def __init__(self, result, msg=None, **kwargs):
        if msg:
            result['detail'] = msg

        self.result = result
        self.msg = msg
        self.__dict__.update(kwargs)
        super(TaskException, self).__init__(result)


class MgmtTaskException(Exception):
    """Custom exception for nice dictionary output"""
    def __init__(self, msg):
        self.result = {'detail': msg}
        self.msg = msg
        super(MgmtTaskException, self).__init__(self.result)


class TaskRetry(Exception):
    """Our task retry exception"""
    pass


class PingFailed(Exception):
    """Task queue ping failed due to timeout or some IO error"""
    pass


class UserTaskError(Exception):
    """Error in que.user_tasks.UserTasks"""
    pass


class CallbackError(Exception):
    """Callback task problem (used by que.callbacks)"""
    pass


class TaskLockError(Exception):
    """Lock error"""
    pass


class NodeError(Exception):
    """General error on compute node"""
    pass
