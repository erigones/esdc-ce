from django.db.models import Count

from vms.models import DcNode, Vm


def get_dc_nodes(request, sr=('dc', 'node'), prefetch_vms_count=False, prefetch_dc=False, order_by=('node__hostname',)):
    qs = DcNode.objects.select_related(*sr).filter(dc=request.dc).order_by(*order_by)

    if prefetch_dc:
        qs = qs.prefetch_related('node__dc')

    if prefetch_vms_count:
        vm_count = dict(Vm.objects.filter(dc=request.dc).values_list('node').annotate(Count('uuid')).order_by())
        real_vm_count = dict(Vm.objects.filter(dc=request.dc, slavevm__isnull=True).values_list('node')
                                       .annotate(Count('uuid')).order_by())

        for dc_node in qs:
            node_uuid = dc_node.node.uuid
            dc_node.vms = vm_count.get(node_uuid, 0)
            dc_node.real_vms = real_vm_count.get(node_uuid, 0)

    return qs
