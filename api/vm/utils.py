from django.db.models import Q
from django.conf import settings

from api.exceptions import NodeIsNotOperational
from api.utils.db import get_object
from gui.models import User
from vms.models import Storage, NodeStorage, Node, Vm, VmTemplate, Image, Subnet, Iso


QNodeNullOrLicensed = Q(node__isnull=True) | ~Q(node__status=Node.UNLICENSED)


def get_vm(request, hostname, attrs=None, where=None, exists_ok=False, noexists_fail=False, sr=('node',), api=True,
           extra=None, check_node_status=('POST', 'PUT', 'DELETE')):
    """
    Call get_object for Vm model identified by hostname. If attributes are not
    specified then set them to check owner and node status.
    Also acts as IsVmOwner permission.
    """
    # Quickly return vm, if set in request (shortcut from GUI)
    vm = getattr(request, '_api_vm', None)
    if api and vm:
        return vm

    if where is None:
        where = QNodeNullOrLicensed

    if attrs is None:
        attrs = {}

    if not request.user.is_admin(request):
        attrs['owner'] = request.user

    attrs['hostname'] = hostname
    attrs['dc'] = request.dc
    attrs['slavevm__isnull'] = True

    if api:
        vm = get_object(request, Vm, attrs, where=where, exists_ok=exists_ok, noexists_fail=noexists_fail, sr=sr,
                        extra=extra)
    else:
        if sr:
            qs = Vm.objects.select_related(*sr)
        else:
            qs = Vm.objects

        if where:
            vm = qs.filter(where).get(**attrs)
        else:
            vm = qs.get(**attrs)

    if check_node_status and request.method in check_node_status:
        if vm.node and vm.node.status not in Node.STATUS_OPERATIONAL:
            raise NodeIsNotOperational

    return vm


def get_vms(request, where=None, sr=('node',), order_by=('hostname',)):
    """
    Return queryset of VMs for current user or all if admin.
    Also acts as IsVmOwner permission.
    """
    if where is None:
        where = QNodeNullOrLicensed

    if sr:
        qs = Vm.objects.select_related(*sr)
    else:
        qs = Vm.objects

    if request.user.is_admin(request):
        return qs.filter(dc=request.dc, slavevm__isnull=True).filter(where).order_by(*order_by)
    else:
        return qs.filter(where).filter(dc=request.dc, owner=request.user, slavevm__isnull=True).order_by(*order_by)


# noinspection PyUnusedLocal
def get_virt_objects(request, model, order_by, dc=None, include=(), **kwargs):
    """
    Return queryset of all public Virt.Objects plus private Virt.Objects for current user.
    Unless you are someone who gets access to all Virt.Objects (staff).

    @type model: django.db.models.Model
    """
    dc = dc or request.dc
    qs = model.objects.filter(dc=dc)

    if request.user.is_admin(request, dc=dc):
        qf = ~Q(access__in=model.INVISIBLE)
    else:
        qf = (Q(access__in=(model.PUBLIC, model.DISABLED))) | (Q(owner=request.user.pk) & Q(access=model.PRIVATE))

    if include:
        qf = qf | Q(pk__in=include)

    return qs.filter(qf).order_by(*order_by)


def get_templates(request, ostype=None, order_by=('id',)):
    if ostype:
        return get_virt_objects(request, VmTemplate, order_by).filter(Q(ostype__isnull=True) | Q(ostype=ostype))
    return get_virt_objects(request, VmTemplate, order_by)


def get_images(request, ostype=None, order_by=('name',), **kwargs):
    if ostype:
        return get_virt_objects(request, Image, order_by, **kwargs).filter(ostype=ostype)
    return get_virt_objects(request, Image, order_by, **kwargs)


def get_subnets(request, order_by=('name',), **kwargs):
    return get_virt_objects(request, Subnet, order_by, **kwargs)


def get_iso_images(request, ostype=None, order_by=('name',)):
    if ostype:
        ostype_filter = Q(ostype__isnull=True) | Q(ostype=ostype)
    else:
        ostype_filter = Q(ostype__isnull=True)

    return get_virt_objects(request, Iso, order_by).filter(ostype_filter)


def get_zpools(request, dc=None, order_by=('zpool',)):
    dc = dc or request.dc
    qs = NodeStorage.objects.filter(dc=dc).order_by(*order_by)

    if request.user.is_admin(request, dc=dc):
        return qs.exclude(storage__access=Storage.DELETED)
    else:
        return qs.filter(
            (Q(storage__access__in=[Storage.PUBLIC, Storage.DISABLED])) |
            (Q(storage__owner=request.user.pk) & Q(storage__access=Storage.PRIVATE))
        )


def get_nodes(request, order_by=('hostname',), **kwargs):
    qs = Node.objects.filter(dc=request.dc)

    if kwargs:
        return qs.filter(**kwargs).order_by(*order_by)

    return qs.order_by(*order_by)


# noinspection PyShadowingBuiltins
def get_owners(request, dc=None, all=False, order_by=('username',)):
    """
    Return QuerySet of all active users. WARNING: Use with care!
    """
    dc = dc or request.dc
    qs = User.objects.exclude(id=settings.SYSTEM_USER).filter(is_active=True).order_by(*order_by)

    if all or dc.access == dc.PUBLIC:
        # Public DC is available for all active users
        return qs

    # Private DC is available to only staff, DC owner and DC admins ...
    admins = User.get_super_admin_ids()
    admins.update(User.get_dc_admin_ids(dc))

    # ... and users who have access to DC:
    return qs.filter(Q(id__in=admins) | Q(roles__in=dc.roles.all()))
