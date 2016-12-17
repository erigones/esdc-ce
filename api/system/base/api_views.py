import os
from logging import getLogger

from django.conf import settings

from api.api_views import APIView
from api.exceptions import ObjectNotFound
from api.task.response import SuccessTaskResponse
from que.utils import read_file

logger = getLogger(__name__)


class SystemLogsView(APIView):
    """api.system.base.views.system_logs"""
    dc_bound = False
    log_path = settings.LOGDIR
    log_files = (
        'auth.log',
        'main.log',
        'task.log',
        'erigonesd-beat.log',
        'mgmt.log',
        'gunicorn-api.access_log',
        'gunicorn-gui.access_log',
        'gunicorn-sio.access_log',
        'gunicorn-api.error_log',
        'gunicorn-gui.error_log',
        'gunicorn-sio.error_log',
    )

    def __init__(self, request, data):
        super(SystemLogsView, self).__init__(request)
        self.data = data
        self.request = request

    def get(self):
        """Function retrieves predefined log files from system"""
        # hardcoded default log files that will be retrieved
        log_files_result = {}
        single_log_file = self.data.get('logname', None)

        if single_log_file:
            # make sure that file is among allowed files,
            # otherwise any file with read permission can be retrieved
            if single_log_file in self.log_files:
                self.log_files = (single_log_file, )
            else:
                logger.error('Error retrieving log file %s, file not among allowed files!', single_log_file)
                raise ObjectNotFound(object_name=single_log_file)

        for log in self.log_files:
            abs_path_name = os.path.join(self.log_path, log)

            try:
                with open(abs_path_name) as f:
                    log_files_result[log] = read_file(f)
            except IOError as exc:
                logger.error('Error retrieving log file %s (%s)', abs_path_name, exc)
                # return an empty string for the log file which raised the exception
                log_files_result[log] = None

        return SuccessTaskResponse(self.request, log_files_result, dc_bound=self.dc_bound)
