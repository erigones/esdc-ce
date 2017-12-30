from api.mon.backends.zabbix.exceptions import (RemoteObjectDoesNotExist, RemoteObjectManipulationError,
                                                MultipleRemoteObjectsReturned)


def parse_zabbix_result(result, key=None, from_get_request=True, many=False, mon_object=None, mon_object_name=None):
    if from_get_request:
        try:
            if not many and len(result) > 1:
                raise MultipleRemoteObjectsReturned('Got multiple (%d) zabbix objects when _one_ was expected' %
                                                    len(result))
            if key:
                return result[0][key]
            else:
                return result[0]
        except (KeyError, IndexError):
            raise RemoteObjectDoesNotExist(mon_object=mon_object, name=mon_object_name)
    else:
        try:
            if many:
                return result[key]
            else:
                return result[key][0]
        except (KeyError, IndexError):
            raise RemoteObjectManipulationError(mon_object=mon_object, name=mon_object_name)
