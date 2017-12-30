from logging import getLogger

from api.signals import dc_settings_changed
from api.api_views import APIView
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.task.utils import TaskID
from api.dc.utils import get_dc_or_404
from api.dc.base.serializers import DcSettingsSerializer, DefaultDcSettingsSerializer
from api.dc.messages import LOG_DC_SETTINGS_UPDATE

logger = getLogger(__name__)


class DcSettingsView(APIView):
    serializer = DcSettingsSerializer

    def __init__(self, request, name, data):
        super(DcSettingsView, self).__init__(request)
        self.data = data
        self.name = name
        self.dc = get_dc_or_404(request, name)
        # Update current datacenter to log tasks for this dc
        request.dc = self.dc

        if self.dc.is_default():
            self.serializer = DefaultDcSettingsSerializer

    def get(self):
        ser = self.serializer(self.request, self.dc)

        return SuccessTaskResponse(self.request, ser.data)

    def put(self):
        dc = self.dc
        ser = self.serializer(self.request, dc, data=self.data, partial=True)

        if not ser.is_valid():
            return FailureTaskResponse(self.request, ser.errors, obj=dc)

        dcs = dc.custom_settings
        dcs.update(ser.settings)
        new_settings = dcs
        old_settings = dc.custom_settings
        dc.custom_settings = dcs
        dc.save()
        data = ser.data  # Prepare ser._data for ser.detail_dict() to work
        res = SuccessTaskResponse(self.request, data, obj=dc, detail_dict=ser.detail_dict(), msg=LOG_DC_SETTINGS_UPDATE)
        task_id = TaskID(res.data.get('task_id'), request=self.request)

        if old_settings != new_settings:
            dc_settings_changed.send(task_id, dc=dc, old_settings=old_settings, new_settings=new_settings)  # Signal!

        return res
