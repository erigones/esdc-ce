from logging import getLogger

from django.utils.six import iteritems
from django.db.models import Q

from api.exceptions import PermissionDenied
from api.dc.utils import get_dc
from api.exceptions import (ObjectNotFound, ObjectAlreadyExists, ItemNotFound, ItemOutOfRange, BadRequest,
                            ItemAlreadyExists)

logger = getLogger(__name__)


# noinspection PyUnusedLocal
def get_object(request, model, attrs, where=None, exists_ok=False, noexists_fail=False, sr=(), pr=(),
               extra=None, annotate=None, create_attrs=None, data=None):
    """
    Get or create object with attrs looked up by where.
    Return error response when needed.
    """
    obj = None

    try:
        if sr:
            qs = model.objects.select_related(*sr)
        else:
            qs = model.objects

        if pr:
            qs = qs.prefetch_related(*pr)

        if annotate:
            qs = qs.annotate(**annotate)

        if extra:
            qs = qs.extra(**extra)

        if where:
            obj = qs.filter(where).get(**attrs)
        else:
            obj = qs.get(**attrs)

    except model.DoesNotExist:
        if request.method in ('GET', 'PUT', 'DELETE') or noexists_fail:
            raise ObjectNotFound(model=model)
        elif request.method == 'POST':
            if create_attrs:
                new_obj_attrs = create_attrs
            else:
                new_obj_attrs = {key: val for key, val in iteritems(attrs) if '__' not in key}
            obj = model(**new_obj_attrs)

    else:
        if request.method == 'POST' and not exists_ok:
            raise ObjectAlreadyExists(model=model)

    return obj


def get_item(request, obj, attr, default=None, name=None):
    """
    Get object item/value. Return error response when needed.
    This can also modify the object, if it's a list => we return it back.
    """
    val = None

    if default is None:
        default = {}

    # noinspection PyBroadException,PyBroadException
    try:
        if isinstance(obj, (dict, tuple, list)):
            val = obj[attr]
        else:
            val = getattr(obj, str(attr))
    except (KeyError, AttributeError, IndexError) as ex:
        if request.method in ('GET', 'PUT', 'DELETE'):
            raise ItemNotFound(object_name=name)
        elif request.method == 'POST':
            if isinstance(ex, IndexError) and isinstance(attr, int):
                if len(obj) == attr:
                    val = default
                    obj.append(val)
                else:
                    raise ItemOutOfRange(object_name=name)
            else:
                val = default
    except:
        raise BadRequest
    else:
        if request.method == 'POST':
            raise ItemAlreadyExists(object_name=name)

    return obj, val


def get_listitem(request, array, array_id, default=None, name=None, max_value=999, min_value=1):
    """
    Call get_item for list. Validate input list index.
    """
    if default is None:
        default = {}

    if array_id > max_value or array_id < min_value:
        raise ItemOutOfRange(object_name=name)

    return get_item(request, array, array_id, default=default, name=name)


def get_virt_object(request, model, sr=('owner', 'dc_bound'), pr=(), order_by=('name',), extra=None, many=False,
                    name=None, get_attrs=None, data=None, where=None, **kwargs):
    """
    Helper function for returning a virt object by get_attrs or queryset of objects. Used in dc-mixed views.
    """
    user = request.user

    if many:
        qs = model.objects.select_related(*sr).prefetch_related(*pr).order_by(*order_by)

        if hasattr(model, 'INTERNAL'):
            qs = qs.filter(~Q(access=model.INTERNAL))

        if not user.is_staff:  # only DC-bound objects are visible by non-superadmin users
            qs = qs.filter(dc_bound__in=request.dcs)  # request.dcs is brought by IsAnyDcPermission

        if where:
            qs = qs.filter(where)

        if extra:
            qs = qs.extra(**extra)

        return qs
    else:
        if get_attrs is None:
            get_attrs = {}

        if name:
            get_attrs['name'] = name

        obj = get_object(request, model, get_attrs, sr=sr, pr=pr, extra=extra, where=where, **kwargs)

        if obj.new:  # POST request
            obj.dc_bound = get_dc(request, data.get('dc', request.dc.name))

        if not user.is_staff:
            if not (obj.dc_bound and obj.dc_bound in request.dcs):  # request.dcs is brought by IsAnyDcPermission
                raise PermissionDenied  # only DC-bound objects are visible by non-superadmin users

        if obj.dc_bound:  # Change DC according to obj.dc_bound flag
            if request.dc != obj.dc_bound:
                request.dc = obj.dc_bound  # Warning: Changing request.dc

                if not user.is_staff:
                    request.dc_user_permissions = request.dc.get_user_permissions(user)

                logger.debug('"%s %s" user="%s" _changed_ dc="%s" permissions=%s', request.method, request.path,
                             user.username, request.dc.name, request.dc_user_permissions)

        return obj
