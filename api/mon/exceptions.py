from django.utils.six import text_type


__all__ = (
    'MonitoringError',
    'InternalMonitoringError',
    'RemoteObjectError',
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
    default_detail = ''

    def __init__(self, detail=None):
        if detail is None:
            self.detail = self.default_detail
        else:
            self.detail = text_type(detail)

    def __str__(self):
        return self.detail

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.detail)


class InternalMonitoringError(MonitoringError):
    """
    Unexpected error from monitoring server.
    """
    pass


class RemoteObjectError(MonitoringError):
    """
    Base class for an error regarding a specific monitoring object.
    """
    default_mon_object = 'Monitoring object'

    def __init__(self, detail=None, mon_object=None, name=None):
        super(RemoteObjectError, self).__init__(detail=detail)

        if mon_object is None:
            mon_object = self.default_mon_object

        if name is None:
            mon_object_name = mon_object
        else:
            mon_object_name = '{} "{}"'.format(mon_object, name)

        self.detail = self.detail.format(mon_object=mon_object_name)
        self.mon_object = mon_object
        self.name = name


class RemoteObjectManipulationError(RemoteObjectError):
    """
    Cannot create, update or delete object in monitoring server.
    """
    default_detail = '{mon_object} manipulation error'


class RemoteObjectDoesNotExist(RemoteObjectError):
    """
    Object does not exist in monitoring server.
    Usually raised when fetching existing object.
    """
    default_detail = '{mon_object} not found'


class RelatedRemoteObjectDoesNotExist(RemoteObjectError):
    """
    Related object does not exist in monitoring server.
    Usually raised when fetching related existing objects for a object that is going to be created or updated.
    """
    default_detail = '{mon_object} not found'


class RemoteObjectAlreadyExists(RemoteObjectError):
    """
    Object cannot be create in monitoring server because it already exists.
    """
    default_detail = '{mon_object} already exists'


class MultipleRemoteObjectsReturned(MonitoringError):
    """
    Expected one object from monitoring server but got more.
    """
    pass
