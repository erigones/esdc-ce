__all__ = (
    'MonitoringError',
    'RemoteObjectManipulationError',
    'RemoteObjectDoesNotExist',
    'RelatedRemoteObjectDoesNotExist',
    'RemoteObjectAlreadyExists',
    'MultipleRemoteObjectsReturned',
)


class MonitoringError(Exception):
    """
    Base monitoring exception. Other monitoring exceptions must inherit from this class.
    """
    pass


class RemoteObjectManipulationError(MonitoringError):
    """
    Cannot create, update or delete object in monitoring server.
    """
    pass


class RemoteObjectDoesNotExist(MonitoringError):
    """
    Object does not exist in monitoring server.
    Usually raised when fetching existing object.
    """
    pass


class RelatedRemoteObjectDoesNotExist(MonitoringError):
    """
    Related object does not exist in monitoring server.
    Usually raised when fetching related existing objects for a object that is going to be created or updated.
    """
    pass


class RemoteObjectAlreadyExists(MonitoringError):
    """
    Object cannot be create in monitoring server because it already exists.
    """
    pass


class MultipleRemoteObjectsReturned(MonitoringError):
    """
    Expected one object from monitoring server but got more.
    """
    pass
