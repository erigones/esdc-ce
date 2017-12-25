from api.mon.backends.zabbix.exceptions import (RemoteObjectDoesNotExist, RemoteObjectManipulationError,
                                                MultipleRemoteObjectsReturned)


def parse_zabbix_result(result, key=None, from_get_request=True, many=False, error_msg=None):
    if from_get_request:
        try:
            if not many and len(result) > 1:
                raise MultipleRemoteObjectsReturned('Got multiple (%d) zabbix objects when _one_ was expected' %
                                                    len(result))
            if key:
                return result[0][key]
            else:
                return result[0]
        except (KeyError, IndexError) as e:
            raise RemoteObjectDoesNotExist(error_msg or e)
    else:
        try:
            if many:
                return result[key]
            else:
                return result[key][0]
        except (KeyError, IndexError) as e:
            raise RemoteObjectManipulationError(error_msg or e)
