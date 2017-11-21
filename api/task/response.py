"""
_TaskResponse child classes are used by api.task.views and the output
depends on the view, but error output should look like this:
    "detail":   "Some error description"

TaskResponse and DummyTaskResponse classes are used by views, that are logged
and generate new tasks and should always produce the following output
(both failed and succeeded tasks):
    "task_id":  "<task_id>",
    "status":   "<celery status>",
    "result":   {},

Other (custom and mainly internal) api views can use simple response classes
defined in api.response, namely: BadRequestResponse, OKRequestResponse,
JSONResponse
"""
from logging import getLogger
from types import NoneType

from django.utils.six import string_types, iteritems
from celery import states

from api import status as scode
from api.response import Response, BadRequestResponse
from api.task.events import TaskCreatedEvent
from api.task.callback import CallbackSerializer, UserCallback
from api.task.utils import (TASK_STATE, TASK_STATE_PENDING, get_task_status, get_task_result, get_task_successful,
                            get_task_error, get_task_exception, task_log)
from que import TT_DUMMY, TG_DC_BOUND, TG_DC_UNBOUND
from que.utils import task_id_from_request, dc_id_from_task_id
from vms.models import Dc

UNUSED_RESPONSE_KWARGS = ('dc_bound', 'tt', 'tg')

logger = getLogger(__name__)


def to_string(x, quote_string=True):
    """Format value so it can be used for task log detail"""
    if isinstance(x, string_types):
        if quote_string:
            return "'%s'" % x
        else:
            return '%s' % x
    elif isinstance(x, bool):
        return str(x).lower()
    elif isinstance(x, (int, float)):
        return str(x)
    elif isinstance(x, NoneType):
        return 'null'
    elif isinstance(x, dict):
        return to_string(','.join('%s:%s' % (to_string(k, quote_string=False), to_string(v, quote_string=False))
                                  for k, v in iteritems(x)))
    elif isinstance(x, (list, tuple)):
        return to_string(','.join(to_string(i, quote_string=False) for i in x))
    return to_string(str(x))


class BaseTaskResponse(Response):
    """
    Base Task response class. Just a wrapper for logging.
    """
    def __init__(self, request, result, task_id, msg='', vm=None, obj=None, owner=None, api_view=None, api_data=None,
                 detail='', detail_dict=None, callback=None, **kwargs):

        if api_view is None:
            api_view = {}

        if api_data is None:
            api_data = {}

        if vm:
            obj = vm

        if task_id:  # Exceptions set the task_id to None
            task_pending = False

            # noinspection PyBroadException
            try:
                t_s = result['status']
            except Exception:
                t_s = None
            # noinspection PyBroadException
            try:
                t_r = result['result']
            except Exception:
                t_r = None

            if msg:  # msg => update task log & save pending user task
                if detail_dict:
                    detail = self.check_detail(detail)
                    detail += self.dict_to_detail(detail_dict)

                detail = self.save_callback(task_id, callback, detail=detail)
                task_pending = task_log(task_id, msg, obj=obj, user=request.user, api_view=api_view,
                                        owner=owner, task_status=t_s, task_result=t_r, detail=detail)

            elif t_s in TASK_STATE_PENDING and obj:  # => save pending user task
                task_pending = True
                self.save_callback(task_id, callback)

                try:
                    obj.tasks_add(task_id, api_view)
                except Exception as e:
                    logger.exception(e)
                    logger.error('Got exception (%s) when updating task %s for %s.', e, task_id, obj)

            if task_pending:  # pending user task => send 'task-created' event
                context = request.parser_context
                # Send celery 'task-created' event, which may be captured by sio.monitor.que_monitor()
                # (this is a replacement for the internal 'task-sent' celery event)
                TaskCreatedEvent(task_id, apiview=api_view, task_status=t_s, task_result=t_r, method=request.method,
                                 view=context['view'].__class__.__name__, siosid=getattr(request, 'siosid', None),
                                 args=context['args'], kwargs=context['kwargs'], apidata=api_data).send()

        for i in UNUSED_RESPONSE_KWARGS:
            try:
                del kwargs[i]
            except KeyError:
                pass

        super(BaseTaskResponse, self).__init__(result, request=request, **kwargs)
        # Set es_task_id header
        self['es_task_id'] = task_id or ''
        # Attributes used by sio.namespaces.APINamespace
        self.apiview = api_view
        self.apidata = api_data

    @staticmethod
    def dict_to_detail(dd):
        if dd:
            return ' '.join([str(key) + '=' + to_string(val) for key, val in iteritems(dd)])
        else:
            return ''

    @staticmethod
    def check_detail(detail):
        if detail:
            detail += ' '
        return detail

    @classmethod
    def save_callback(cls, task_id, callback_data, detail=None):
        if callback_data:
            ser = CallbackSerializer(data=callback_data)
            dc_settings = Dc.objects.get_by_id(dc_id_from_task_id(task_id)).settings

            if detail is not None and dc_settings.API_LOG_USER_CALLBACK:
                log_callback = True
            else:
                log_callback = False

            if ser.is_valid():
                UserCallback(task_id).save(ser.data.copy(), cb_log=log_callback)
                msg = ser.data
            else:
                msg = ser.errors

            if log_callback:
                detail = cls.check_detail(detail)
                detail += cls.dict_to_detail(msg)

        return detail


class TaskResponse(BaseTaskResponse):  # Use this
    """
    Response class for task calls. Called by all api views, except api.task.views.
    """
    def __init__(self, request, task_id, data=None, **kwargs):
        result, kwargs['status'] = get_task_status(task_id, get_task_result)
        self.task_status = False  # APISyncMiddleware should wait for the task

        if data is not None and 'cb_url' in data:
            cb = data
        else:
            cb = None

        super(TaskResponse, self).__init__(request, result, task_id, callback=cb, **kwargs)
        self['es_task_response'] = 'true'


class DummyTaskResponse(BaseTaskResponse):
    """
    Response class for non task calls.
    """
    def __init__(self, request, result, task_id=None, tt=TT_DUMMY, dc_bound=True, **kwargs):
        if 'task_status' in kwargs:
            task_status = kwargs.pop('task_status')
        else:
            task_status = states.PENDING

        if isinstance(result, Exception):
            tr, kwargs['status'] = get_task_exception(result)
        else:
            if 'status' not in kwargs:
                kwargs['status'] = TASK_STATE[task_status]

            if task_id is None:
                task_id = self.gen_task_id(request, tt=tt, dc_bound=dc_bound, **kwargs)

            tr = {
                'task_id': task_id,
                'status': task_status,
                'result': result,
            }

        super(DummyTaskResponse, self).__init__(request, tr, task_id, **kwargs)

    # noinspection PyUnusedLocal
    @staticmethod
    def _get_owner_id(vm=None, obj=None, owner=None, **kwargs):
        if owner is not None:
            return owner.id

        if vm:
            obj = vm

        if obj is not None and hasattr(obj, 'owner'):
            return obj.owner.id

        return None

    @classmethod
    def gen_task_id(cls, request, tt=TT_DUMMY, dc_bound=True, **kwargs):
        if dc_bound:
            tg = TG_DC_BOUND
        else:
            tg = TG_DC_UNBOUND

        return task_id_from_request(request, owner_id=cls._get_owner_id(**kwargs), tt=tt, tg=tg, dummy=True)


class SuccessTaskResponse(DummyTaskResponse):  # Use this
    def __init__(self, request, result, **kwargs):
        kwargs['task_status'] = states.SUCCESS
        super(SuccessTaskResponse, self).__init__(request, result, **kwargs)


class FailureTaskResponse(DummyTaskResponse):  # Use this
    def __init__(self, request, result, **kwargs):
        kwargs['task_status'] = states.FAILURE
        super(FailureTaskResponse, self).__init__(request, result, **kwargs)


#
# Response classes used only by api.task.views
#

class SimpleTaskResponse(Response):
    """
    Base Task response class used by /task response classes.
    """
    # noinspection PyUnusedLocal
    def __init__(self, request, result, task_status, **kwargs):
        self.task_status = True  # APISyncMiddleware should response immediately

        # You can override the HTTP status code
        if 'status' not in kwargs:
            kwargs['status'] = task_status

        super(SimpleTaskResponse, self).__init__(result, request=request, **kwargs)


class TaskStatusResponse(SimpleTaskResponse):
    """
    Response class for task calls. Called by api.task.views.task_status.
    """
    def __init__(self, request, task_id, **kwargs):
        result, status = get_task_status(task_id, get_task_result)
        super(TaskStatusResponse, self).__init__(request, result, status, **kwargs)
        self['es_task_response'] = 'true'


class TaskDoneResponse(SimpleTaskResponse):
    """
    Response class for task calls. Called by api.task.views.task_done.
    """
    def __init__(self, request, task_id, **kwargs):
        result, status = get_task_status(task_id, get_task_successful)
        super(TaskDoneResponse, self).__init__(request, result, status, **kwargs)


class TaskFailureResponse(SimpleTaskResponse):
    """
    Response class for error task calls. Called by some api.task.views.
    """
    def __init__(self, request, message, **kwargs):
        result, status = get_task_error(message)
        super(TaskFailureResponse, self).__init__(request, result, status, **kwargs)


class TaskSuccessResponse(SimpleTaskResponse):
    """
    Response class for succeeded task calls. Called by some api.task.views.
    """
    def __init__(self, request, result, **kwargs):
        status = scode.HTTP_200_OK
        super(TaskSuccessResponse, self).__init__(request, result, status, **kwargs)


#
# Response factory functions
#
def task_response(request, task_id, error, data=None, **kwargs):
    """
    Response class factory for classic task calls. Called by some api views.
    """
    if error:
        return FailureTaskResponse(request, error, **kwargs)
    elif task_id:
        return TaskResponse(request, task_id, data=data, **kwargs)
    else:
        return BadRequestResponse(request)


def mgmt_task_response(request, task_id, error, result, data=None, **kwargs):
    """
    Response class factory for mgmt task calls. Called by some api views.
    """
    if result:
        return SuccessTaskResponse(request, result, **kwargs)
    elif error:
        return FailureTaskResponse(request, error, **kwargs)
    elif task_id:
        return TaskResponse(request, task_id, data=data, **kwargs)
    else:
        return BadRequestResponse(request)
