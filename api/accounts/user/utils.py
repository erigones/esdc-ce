from django.db.models import Q
from django.conf import settings

from api.exceptions import PermissionDenied
from api.utils.db import get_object, get_virt_object
from api.accounts.messages import LOG_USER_UPDATE
from gui.models import User, UserProfile
from que import TG_DC_UNBOUND
from que.utils import task_id_from_task_id

ExcludeInternalUsers = ~Q(id=settings.SYSTEM_USER)
ExcludeInternalProfileUsers = ~Q(user__id=settings.SYSTEM_USER)


def get_user(request, username, where=None, **kwargs):
    user = request.user

    if where:
        where = where & ExcludeInternalUsers
    else:
        where = ExcludeInternalUsers

    if getattr(request, 'is_profile_owner', False):
        if user.username == username:  # IsProfileOwner
            return get_object(request, User, {'username': username}, where=where, **kwargs)
        else:
            raise PermissionDenied
    else:  # Is SuperAdmin or UserAdmin
        return get_virt_object(request, User, get_attrs={'username': username}, where=where, **kwargs)


def get_users(request, where=None, **kwargs):
    if where:
        where = where & ExcludeInternalUsers
    else:
        where = ExcludeInternalUsers

    return get_virt_object(request, User, many=True, where=where, **kwargs)


def get_user_profiles(request, where=None, **kwargs):
    if where:
        where = where & ExcludeInternalProfileUsers
    else:
        where = ExcludeInternalProfileUsers

    return get_virt_object(request, UserProfile, many=True, where=where, **kwargs)


def remove_user_dc_binding(task_id, user, dc=None):
    """Remove user.dc_bound flag"""
    from api.task.utils import task_log_success  # circular imports

    if not user.dc_bound or (dc and user.dc_bound == dc):  # Nothing to do
        return None

    dc_id = user.dc_bound.id
    user.dc_bound = None
    user.save(update_fields=('dc_bound',))

    task_id = task_id_from_task_id(task_id, tg=TG_DC_UNBOUND, dc_id=dc_id, keep_task_suffix=True)
    task_log_success(task_id, LOG_USER_UPDATE, obj=user, update_user_tasks=False, detail='dc_bound=false')
