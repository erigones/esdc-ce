from logging import getLogger

from api.api_views import APIView
from api.exceptions import PreconditionRequired
from api.system.messages import LOG_SYSTEM_UPDATE
from api.system.update.serializers import UpdateSerializer
from api.system.update.tasks import system_update
from api.task.response import FailureTaskResponse, mgmt_task_response
from que import TG_DC_UNBOUND

logger = getLogger(__name__)


class UpdateView(APIView):
    """
    Update Danube Cloud application.
    """
    LOCK = 'system_update'
    dc_bound = False

    def __init__(self, request, data):
        super(UpdateView, self).__init__(request)
        self.data = data

    @classmethod
    def is_task_running(cls):
        return system_update.get_lock(cls.LOCK).exists()

    def put(self):
        assert self.request.dc.is_default()

        ser = UpdateSerializer(self.request, data=self.data)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, dc_bound=False)

        version = ser.data['version']
        from core.version import __version__ as mgmt_version
        # noinspection PyUnboundLocalVariable
        if version == ('v' + mgmt_version) and not ser.data.get('force'):
            raise PreconditionRequired('System is already up-to-date')

        obj = self.request.dc
        msg = LOG_SYSTEM_UPDATE
        _apiview_ = {
            'view': 'system_update',
            'method': self.request.method,
            'version': version,
        }
        meta = {
            'apiview': _apiview_,
            'msg': LOG_SYSTEM_UPDATE,
        }
        task_kwargs = ser.data.copy()
        task_kwargs['dc_id'] = obj.id

        tid, err, res = system_update.call(self.request, None, (), kwargs=task_kwargs, meta=meta,
                                           tg=TG_DC_UNBOUND, tidlock=self.LOCK)
        if err:
            msg = obj = None  # Do not log an error here

        return mgmt_task_response(self.request, tid, err, res, msg=msg, obj=obj, api_view=_apiview_, dc_bound=False,
                                  data=self.data, detail_dict=ser.detail_dict(force_full=True))
