from logging import getLogger

from django.conf import settings
from django.http.response import StreamingHttpResponse
from gevent import sleep

from api.status import HTTP_201_CREATED
from api.task.response import TaskResponse
from api.task.utils import is_dummy_task, get_task_status, get_task_result
from api.task.views import task_status
from api.utils.request import set_request_method

logger = getLogger(__name__)

ES_STREAM_CLIENT = 'es'


def task_status_loop(request, response, task_id, stream=None):
    """
    Loop and check for task result. Send keep-alive whitespace for every loop.
    TODO: Trailing headers are not supported, so status code cannot be changed.
    """
    logger.debug('Starting APISyncMiddleware loop (%s)', request.path)
    logger.info('Waiting for pending task %s status in "%s" streaming loop', task_id, stream)
    elapsed = 0

    # Task check loop
    while elapsed < settings.API_SYNC_TIMEOUT:
        if elapsed > 1200:
            nap = 30
        elif elapsed > 60:
            nap = 12
        elif elapsed > 30:
            nap = 6
        elif elapsed > 5:
            nap = 3
        else:
            nap = 1

        sleep(nap)
        elapsed += nap

        result, status = get_task_status(task_id, get_task_result)
        logger.debug('APISyncMiddleware loop (%s) status: %s', request.path, status)

        if status != HTTP_201_CREATED:
            logger.debug('APISyncMiddleware loop finished (%s) in %d seconds', request.path, elapsed)
            logger.info('Task %s finished', task_id)
            request = set_request_method(request, 'GET')
            res = task_status(request, task_id=task_id)

            if stream == ES_STREAM_CLIENT:
                yield '%d\n' % res.status_code  # new status code (es knows how to interpret this)

            yield res.rendered_content  # will call render()
            break
        else:
            yield ' '  # keep-alive

    else:  # Timeout
        logger.debug('APISyncMiddleware loop finished with timeout (%s)', request.path)
        logger.warning('Task %s is running too long; no point to wait', task_id)
        yield response  # is already rendered


class APISyncMiddleware(object):
    """
    Provide synchronous API. Convert asynchronous responses to synchronous by
    periodically checking task results. Only for HTTP requests to /api/...
    """
    # noinspection PyMethodMayBeStatic
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Check if response has information about regular pending task.
        Loop and check for task result if task_id of a PENDING task is found.
        """
        # Ignore socket.io requests
        if not request.path.startswith('/api/'):
            return None

        response = view_func(request, *view_args, **view_kwargs)

        # Valid task response is always a TaskResponse objects
        if not isinstance(response, TaskResponse):
            return response

        # api.task.views.task_status should immediately show task status
        if response.task_status:
            return response

        # Only if task/status is PENDING
        if response.status_code != HTTP_201_CREATED:
            return response

        # We need the task_id
        # noinspection PyBroadException
        try:
            task_id = response.data['task_id']
        except:
            return response

        # This should never happen (Dummy task has it's own Response class)
        if is_dummy_task(task_id):
            return response

        # Use streaming only if client is es or es compatible
        stream = request.META.get('HTTP_ES_STREAM', None)

        if stream:
            # Let's render the pending response as it sets some headers (Content-type)
            pending_response = response.rendered_content
            # Switch to streaming response
            stream_res = StreamingHttpResponse(task_status_loop(request, pending_response, task_id, stream=stream),
                                               status=HTTP_201_CREATED)
            # Copy headers
            # noinspection PyProtectedMember
            stream_res._headers = response._headers
            # Set custom es_stream header => es will process the stream correctly
            stream_res['es_stream'] = bool(stream)
            stream_res['es_task_id'] = task_id

            return stream_res
        else:
            return response
