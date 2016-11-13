from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.http import HttpResponse

from gui.decorators import staff_required, ajax_required, admin_required, profile_required
from gui.utils import collect_view_data, redirect, get_query_string
from gui.dc.storage.forms import StorageForm
from vms.models import NodeStorage, DcNode

SR = ('node', 'storage', 'storage__owner')
OB = ('node__hostname', 'zpool')


@login_required
@admin_required
@profile_required
def dc_storage_list(request):
    """
    Storage management.
    """
    context = collect_view_data(request, 'dc_storage_list')
    context['can_edit'] = can_edit = request.user.is_staff  # DC owners have read-only rights
    context['all'] = _all = can_edit and request.GET.get('all', False)
    context['qs'] = get_query_string(request, all=_all).urlencode()
    nss = NodeStorage.objects.select_related(*SR).order_by(*OB)
    dc_nodes = dict([(dn.node.hostname, dn) for dn in DcNode.objects.select_related('node').filter(dc=request.dc)])

    if _all:
        context['storages'] = storages = nss.prefetch_related('dc')
        # Uses set() because of optimized membership ("in") checking
        context['dc_storages'] = set(nss.exclude(dc=request.dc).values_list('pk', flat=True))
    else:
        context['storages'] = storages = nss.filter(dc=request.dc)

    # Bug #chili-525
    for ns in storages:
        ns.set_dc_node(dc_nodes.get(ns.node.hostname, None))
        ns.set_dc(request.dc)

    if can_edit:
        context['form'] = form = StorageForm(request, storages)
        context['node_zpool'] = form.node_zpool
    else:
        context['node_zpool'] = {}

    return render(request, 'gui/dc/storage_list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def dc_storage_form(request):
    """
    Ajax page for creating or updating storages.
    """
    nss = NodeStorage.objects.select_related(*SR).filter(dc=request.dc).order_by(*OB)
    form = StorageForm(request, nss, request.POST)

    if form.is_valid():
        status = form.save(args=(form.zpool_node,))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('dc_storage_list', query_string=request.GET)

    return render(request, 'gui/dc/storage_form.html', {'form': form})
