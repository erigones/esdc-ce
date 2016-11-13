from django.http import Http404
from django.db.models import Q

from api.exceptions import ObjectNotFound
from vms.models import Dc, DomainDc
from gui.models import Role
from pdns.models import Domain
from que import TG_DC_BOUND, TG_DC_UNBOUND
from que.utils import task_id_from_task_id


def get_dc(request, dc_name):
    """Return Datacenter from request"""
    try:
        dc = Dc.objects.get_by_name(dc_name)
        user = request.user

        if not (user.is_staff or dc.access == Dc.PUBLIC or dc == user.current_dc or user == dc.owner):
            if not dc.roles.filter(pk__in=user.roles.all()).exists():
                raise Dc.DoesNotExist
    except Dc.DoesNotExist:
        raise ObjectNotFound(model=Dc)

    return dc


# noinspection PyUnusedLocal
def get_dc_or_404(request, dc_name, api=True):
    """
    Get Dc for editing purposes.
    """
    try:
        return Dc.objects.get_by_name(dc_name)
    except Dc.DoesNotExist:
        if api:
            raise ObjectNotFound(model=Dc)
        else:
            raise Http404


def get_dcs(request, sr=(), pr=(), order_by=('name',), annotate=None, extra=None):
    """Return queryset of available Datacenters for current user"""
    if sr:
        # noinspection PyArgumentList
        qs = Dc.objects.distinct().select_related(*sr)
    else:
        qs = Dc.objects.distinct()

    if pr:
        qs = qs.prefetch_related(*pr)

    if request.user.is_staff:
        qs = qs.exclude(access=Dc.DELETED).order_by(*order_by)
    else:
        qs = qs.filter(
            Q(access=Dc.PUBLIC) |
            (Q(owner=request.user.pk) & Q(access=Dc.PRIVATE)) |
            Q(roles__in=request.user.roles.all())
        ).order_by(*order_by)

    if annotate:
        qs = qs.annotate(**annotate)

    if extra:
        qs = qs.extra(**extra)

    return qs


def attach_dc_virt_object(task_id, msg, obj, dc, user=None):
    """Attach object into DC and log it"""
    from api.task.utils import task_log_success  # circular imports

    if isinstance(obj, Domain):
        DomainDc.objects.create(dc=dc, domain_id=obj.id)
    elif isinstance(obj, Role):
        obj.dc_set.add(dc)
    else:
        obj.dc.add(dc)

    task_id = task_id_from_task_id(task_id, tg=TG_DC_BOUND, dc_id=dc.id, keep_task_suffix=True)
    task_log_success(task_id, msg, obj=obj, owner=getattr(obj, 'owner', None), user=user, update_user_tasks=False,
                     detail="dc='%s'" % dc.name)


def remove_dc_binding_virt_object(task_id, msg, obj, user=None, dc_id=None):
    """Detach object from DC and log it"""
    from api.task.utils import task_log_success  # circular imports

    if dc_id is None:
        if isinstance(obj, Domain):
            dc_id = obj.dc_bound
        else:
            dc_id = obj.dc_bound.id

    obj.dc_bound = None
    obj.save(update_fields=('dc_bound', 'changed'))

    task_id = task_id_from_task_id(task_id, tg=TG_DC_UNBOUND, dc_id=dc_id, keep_task_suffix=True)
    task_log_success(task_id, msg, obj=obj, owner=getattr(obj, 'owner', None), user=user, update_user_tasks=False,
                     detail='dc_bound=false')
