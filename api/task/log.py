from django.core.cache import cache
from django.db.models import Q
from django.conf import settings

from vms.models import TaskLogEntry
from gui.models import User
from que import TT, TG, TG_DC_UNBOUND

TASK_TYPE = '%d%02d'
MSG_UPDATE = ('Update', 'Rollback', 'Restore', 'Revert')
MSG_CREATE = ('Add', 'Create', 'Recreate', 'Import')
MSG_DELETE = ('Remove', 'Delete', 'Invalid')
MSG_REMOTE = 'Remote'


def _cache_log_key(owner_id, dc_id):
    """Return the key for tasklog in cache"""
    return settings.TASK_LOG_BASENAME + '.' + str(owner_id) + '.' + str(dc_id)


def _cache_log(key, msgdict):
    """Save msgdict into owner_ids cache"""
    lastlog = cache.get(key)

    if lastlog is None or not isinstance(lastlog, list):
        lastlog = []
    elif len(lastlog) >= settings.TASK_LOG_LASTSIZE:
        lastlog.pop(0)

    lastlog.append(msgdict)
    cache.set(key, lastlog)


def log(msgdict):
    """
    Save msgdict into DB and cache.
    """
    # This dictionary can be stored more than once
    dct = msgdict.copy()

    # DB
    TaskLogEntry.add(**msgdict)

    # Do not store PKs in cache
    dc_id = dct.pop('dc_id')
    owner_id = dct.pop('owner_id')
    del dct['user_id']
    del dct['object_pk']
    del dct['content_type']
    dct['time'] = dct['time'].isoformat()

    # Always store everything in staff cached task log
    _cache_log(_cache_log_key(settings.TASK_LOG_STAFF_ID, dc_id), dct)

    # Store owner relevant actions in owners cached task log
    if owner_id not in User.get_super_admin_ids():
        _cache_log(_cache_log_key(owner_id, dc_id), dct)


def _get_task_type(tg, tt):
    """Convert task group and task type into task log type number"""
    return int(TASK_TYPE % (TG.index(tg), TT.index(tt)))


def task_type_from_task_prefix(task_prefix):
    """
    Convert task_prefix to task log type.
    """
    return _get_task_type(task_prefix[3], task_prefix[1])


def get_task_types(tt=TT, tg=TG):
    """
    Return list of task flags
    """
    return [_get_task_type(g, t) for g in tg for t in tt]


def task_flag_from_task_msg(msg):
    """
    Create task log flag from task message.
    """
    if msg.startswith(MSG_UPDATE):
        return TaskLogEntry.UPDATE
    elif msg.startswith(MSG_CREATE):
        return TaskLogEntry.CREATE
    elif msg.startswith(MSG_DELETE):
        return TaskLogEntry.DELETE
    elif msg.startswith(MSG_REMOTE):
        return TaskLogEntry.REMOTE
    return TaskLogEntry.OTHER


def get_tasklog(request, sr=('content_type',), filter_by_permissions=True, order_by=('-time',), q=None, **where):
    """
    Return TaskLogEntry queryset.
    """
    if q is False:
        return TaskLogEntry.objects.none()

    qs = TaskLogEntry.objects.select_related(*sr).order_by(*order_by)

    if filter_by_permissions:
        if request.user.is_staff and request.dc.is_default():
            qs = qs.filter((Q(dc=request.dc) | Q(task_type__in=get_task_types(tg=TG_DC_UNBOUND))))
        else:
            qs = qs.filter(dc=request.dc)

        if not request.user.is_admin(request):
            qs = qs.filter(owner_id=request.user.id)

    if q:
        qs = qs.filter(q)

    if where:
        qs = qs.filter(**where)

    return qs


def get_tasklog_cached(request):
    """
    Always return a list of log lines from cache.
    """
    if request.user.is_admin(request):
        key = _cache_log_key(settings.TASK_LOG_STAFF_ID, request.dc.id)
    else:
        key = _cache_log_key(request.user.id, request.dc.id)

    res = cache.get(key)

    if res is None or not isinstance(res, list):
        return []

    res.reverse()
    return res


def delete_tasklog_cached(dc_id, user_id=None):
    """
    Remove tasklog cache entry.
    """
    if user_id:
        key = _cache_log_key(user_id, dc_id)
    else:
        key = _cache_log_key(settings.TASK_LOG_STAFF_ID, dc_id)

    return cache.delete(key)
