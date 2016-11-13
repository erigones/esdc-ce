from api.permissions import DcBasePermission
from vms.models import Dc
from que.utils import user_owner_dc_ids_from_task_id


class IsUserTask(DcBasePermission):
    """
    Check if user has permissions to work with the task.
    The task_id reveals the user ID of the task's creator, the owner ID and the DC owner ID of the task object.
    Unless we support groups, we just compare it with the current user.
    """
    def has_permission(self, request, view, args, kwargs):
        task_id = kwargs.get('task_id', None)

        if not task_id:
            return False

        user_id, owner_id, dc_id = user_owner_dc_ids_from_task_id(task_id)
        request_user_id = str(request.user.id)

        if not user_id or not owner_id:
            return False

        try:
            dc_id = int(dc_id)
        except ValueError:
            return False

        if request.user.is_admin(request, dc=Dc.objects.get_by_id(dc_id)):
            return True

        return user_id == request_user_id or owner_id == request_user_id


class IsTaskCreator(DcBasePermission):
    """
    Check if the user is the creator of the task.
    """
    def has_permission(self, request, view, args, kwargs):
        task_id = kwargs.get('task_id', None)

        if not task_id:
            return False

        user_id, owner_id, dc_id = user_owner_dc_ids_from_task_id(task_id)

        if not user_id or not owner_id:
            return False

        try:
            dc_id = int(dc_id)
        except ValueError:
            return False

        if request.user.is_admin(request, dc=Dc.objects.get_by_id(dc_id)):
            return True

        return user_id == str(request.user.id)
