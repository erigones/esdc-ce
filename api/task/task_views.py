from time import sleep

from api import status
from que.utils import user_owner_dc_ids_from_task_id
from que.user_tasks import UserTasks
from api.decorators import api_view, request_data
from api.serializers import ForceSerializer
from api.permissions import IsSuperAdminOrReadOnly
from api.task.response import TaskStatusResponse, TaskDoneResponse, TaskSuccessResponse, TaskFailureResponse
from api.task.permissions import IsUserTask, IsTaskCreator
from api.task.utils import get_user_tasks, cancel_task, delete_task
from api.task.serializers import TaskCancelSerializer
from api.task.task_log import TaskLogView

__all__ = ('task_list', 'task_details', 'task_status', 'task_done', 'task_cancel', 'task_log', 'task_log_report')


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data()  # get_user_tasks = IsUserTask
def task_list(request, data=None):
    """
    Show a list (:http:get:`GET </task>`) of pending user tasks.

    .. http:get:: /task

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |UserTask|
        :Asynchronous?:
            * |async-no|
        :status 200: List of running tasks
        :status 403: Forbidden
    """
    return TaskSuccessResponse(request, get_user_tasks(request))  # Displays tasks from current datacenter only


# noinspection PyUnusedLocal
@api_view(('GET', 'DELETE'))
@request_data(permissions=(IsSuperAdminOrReadOnly, IsUserTask))
def task_details(request, task_id=None, data=None):
    """
    Show (:http:get:`GET </task/(task_id)>`) task details of a pending task or
    delete (:http:delete:`DELETE </task/(task_id)>`) a started task.

    .. http:get:: /task/(task_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |UserTask|
        :Asynchronous?:
            * |async-no|
        :status 200: Object with task details
        :status 403: Forbidden
        :status 404: Task does not exist

    .. http:delete:: /task/(task_id)

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |SuperAdmin|
        :Asynchronous?:
            * |async-no|
        :arg data.force: Force task deletion. USE WITH CAUTION! (default: false)
        :type data.force: boolean
        :status 200: Delete pending
        :status 403: Forbidden
        :status 404: Task does not exist
        :status 406: Task cannot be deleted

    """
    user_id, owner_id, dc_id = user_owner_dc_ids_from_task_id(task_id)
    res = UserTasks(owner_id).get(task_id)

    if not res or int(dc_id) != request.dc.id:
        return TaskFailureResponse(request, 'Task does not exist', status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        apiview = res.get('apiview', {})
        apiview['task_id'] = task_id

        return TaskSuccessResponse(request, apiview)

    elif request.method == 'DELETE':
        force = ForceSerializer(data=data, default=False).is_true()
        tid, err = delete_task(task_id, force=force)

        if err:
            return TaskFailureResponse(request, err, status=status.HTTP_406_NOT_ACCEPTABLE)
        else:
            return TaskSuccessResponse(request, 'Delete pending')


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsUserTask,))
def task_status(request, task_id=None, data=None):
    """
    Returns (:http:get:`GET </task/(task_id)/status>`) task status and task result.

    .. http:get:: /task/(task_id)/status

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |UserTask|
        :Asynchronous?:
            * |async-no|
        :arg string task_id: **required** - Task ID
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 410: REVOKED
        :status 403: Forbidden
        :status 404: Task does not exist
    """
    return TaskStatusResponse(request, task_id)


# noinspection PyUnusedLocal
@api_view(('GET',))
@request_data(permissions=(IsUserTask,))
def task_done(request, task_id=None, data=None):
    """
    Returns (:http:get:`GET </task/(task_id)/done>`) task execution status (true or false).
    This is not really useful, because :func:`api.task.views.task_status` overrides and improves this functionality.

    .. http:get:: /task/(task_id)/done

        :DC-bound?:
            * |dc-no|
        :Permissions:
            * |UserTask|
        :Asynchronous?:
            * |async-no|
        :arg string task_id: **required** - Task ID
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 410: REVOKED
        :status 403: Forbidden
        :status 404: Task does not exist
    """
    return TaskDoneResponse(request, task_id)


@api_view(('PUT',))
@request_data(permissions=(IsTaskCreator,))
def task_cancel(request, task_id=None, data=None):
    """
    Revoke (:http:put:`PUT </task/(task_id)/cancel>`) a task and return task
    status from :func:`api.task.views.task_status` on success.

    .. http:put:: /task/(task_id)/cancel

        :DC-bound?:
            * |dc-yes|
        :Permissions:
            * |TaskCreator|
        :Asynchronous?:
            * |async-no|
        :arg string task_id: **required** - Task ID
        :status 200: SUCCESS
        :status 201: PENDING
        :status 400: FAILURE
        :status 410: REVOKED
        :status 403: Forbidden
        :status 404: Task does not exist
        :status 406: Task cannot be cancelled
    """
    # Task must exist in pending user tasklist
    if task_id in get_user_tasks(request):
        ser = TaskCancelSerializer(data=data)

        if ser.is_valid() and ser.data['force']:
            cancel_task(task_id, True)
        else:
            cancel_task(task_id, False)

        sleep(1)  # Let's give the task queue some time to update revoked state

        return TaskStatusResponse(request, task_id)

    return TaskFailureResponse(request, 'Task cannot be canceled', status=status.HTTP_406_NOT_ACCEPTABLE)


@api_view(('GET',))
@request_data()
def task_log(request, data=None):
    """
    Display (:http:get:`GET </task/log>`) the task log.

    .. http:get:: /task/log

        .. note:: Task log filters below are available only when displaying task log entries from DB \
(using the **page** attribute).

        :DC-bound?:
            * |dc-yes|
        :Permissions:
        :Asynchronous?:
            * |async-no|
        :arg data.page: Page number to fetch. Each page has 100 log entries \
(default: null - last 10 log entries from cache)
        :type data.page: integer
        :arg data.status: Filter task log entries by status (default: "")
        :type data.status: string (one of: PENDING, SUCCESS, FAILURE, REVOKED)
        :arg data.object_type: Filter task log entries by object type (default: "")
        :type data.object_type: string (one of: \
dc, vm, node, nodestorage, subnet, image, vmtemplate, iso, domain, user, role)
        :arg data.object_name: Filter by object name; ``object_type`` is required for this filter to work (default: "")
        :type data.object_name: string
        :arg data.show_running: Show only running tasks (default: false)
        :type data.show_running: boolean
        :arg data.hide_auto: Hide automatic tasks (default: false)
        :type data.hide_auto: boolean
        :arg data.date_from: Show task log entries older than date (YYYY-MM-DD) specified (default: null)
        :type data.date_from: string (date in ISO 8601 format)
        :arg data.date_to: Show task log entries created before date (YYYY-MM-DD) specified (default: null)
        :type data.date_to: string (date in ISO 8601 format)
        :arg data.order_by: :ref:`Available fields for sorting <order_by>`: ``time`` (default: ``-time``)
        :type data.order_by: string
        :status 200: Object with "results" attribute - list of log lines
        :status 400: Error object with "detail" attribute or with invalid filter attributes
        :status 403: Forbidden
    """
    return TaskLogView(request, data=data).get()


@api_view(('GET',))
@request_data()
def task_log_report(request, data=None):
    """
    Display (:http:get:`GET </task/log/report>`) task log statistics.

    .. http:get:: /task/log/report

        :DC-bound?:
            * |dc-yes|
        :Permissions:
        :arg data.last: Use task log entries which are n seconds old (default: 86400)
        :type data.last: integer
        :status 200: Object with *succeeded*, *failed*, *pending* and *revoked* attributes
        :status 400: Error object with "detail" attribute
        :status 403: Forbidden
    """
    return TaskLogView(request, data=data).report()
