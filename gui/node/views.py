from itertools import chain

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.db.models import Count, Q
from django.http import HttpResponse, Http404, QueryDict
from django.conf import settings

from vms.models import Node, NodeStorage, Storage, TaskLogEntry, Vm
from gui.decorators import staff_required, ajax_required
from gui.utils import collect_view_data, get_pager, reverse
from gui.signals import view_node_list, view_node_details
from gui.node.forms import (NodeStatusForm, NodeForm, NodeStorageForm, UpdateBackupForm, NodeStorageImageForm,
                            BackupFilterForm)
from gui.node.utils import get_dc1_settings, get_nodes_extended, get_node, get_node_bkpdefs, get_node_backups
from gui.vm.forms import RestoreBackupForm
from gui.vm.utils import get_vms
from gui.dc.views import dc_switch
from gui.tasklog.utils import get_tasklog
from api.decorators import setting_required
from api.mon.utils import MonitoringGraph as Graph


@login_required
@staff_required
def node_list(request):
    """
    List of all compute nodes.
    """
    context = collect_view_data(request, 'node_list')
    context['nodes'] = Node.all()
    context['node_list'] = get_nodes_extended(request)
    context['status_form'] = NodeStatusForm(request, None)

    view_node_list.send(sender='gui.node.views.list', request=request, context=context)

    return render(request, 'gui/node/list.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def status_form(request):
    """
    Ajax page for changing status of compute nodes.
    """
    form = NodeStatusForm(request, None, request.POST)

    if form.is_valid():
        res = [form.call_node_define(hostname) == 200 for hostname in form.cleaned_data['hostnames']]

        if all(res):
            if request.GET.get('current_view', None) == 'maintenance':
                redirect_view = 'system_maintenance'
            else:
                redirect_view = 'node_list'

            return redirect(redirect_view)

    return render(request, 'gui/node/status_form.html', {'form': form})


@login_required
@staff_required
def details(request, hostname):
    """
    Compute node details.
    """
    dc1_settings = get_dc1_settings(request)
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname, sr=('owner',))
    context['nodes'] = Node.all()
    context['node_dcs'] = node.dc.all().values_list('alias', flat=True)
    context['node_vms'] = node.vm_set.count()
    context['node_real_vms'] = node.vm_set.filter(slavevm__isnull=True).count()
    context['form'] = NodeForm(request, node, initial=node.web_data)
    context['mon_sla_enabled'] = settings.MON_ZABBIX_ENABLED and dc1_settings.MON_ZABBIX_NODE_SLA

    if node.is_backup:
        context['node_backups'] = node.backup_set.count()
    else:
        context['node_backups'] = 0

    view_node_details.send(sender='gui.node.views.details', request=request, context=context)

    return render(request, 'gui/node/details.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def define_form(request, hostname):
    """
    Ajax page for updating compute node settings.
    """
    node = get_node(request, hostname, sr=('owner',))
    form = NodeForm(request, node, request.POST)

    if form.is_valid():
        status = form.save(args=(hostname,))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            if form.action == 'delete':
                return redirect('node_list')
            else:
                return redirect('node_details', hostname)

    return render(request, 'gui/node/define_form.html', {'form': form})


@login_required
@staff_required
def storages(request, hostname):
    """
    List of node storages.
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = Node.all()
    context['zpools'] = node.zpools.keys()
    context['zpools_missing'] = []
    context['storages'] = node.nodestorage_set.select_related('storage', 'storage__owner').order_by('zpool')\
                                              .annotate(Count('dc', distinct=True))
    context['form'] = NodeStorageForm(request, node, None, initial={
        'node': node.hostname,
        'owner': request.user.username,
        'access': Storage.PUBLIC,
        'size_coef': Storage.SIZE_COEF,
    })

    for ns in context['storages']:
        try:
            context['zpools'].remove(ns.zpool)
        except ValueError:
            context['zpools_missing'].append(ns.zpool)  # zpool vanished from node

    return render(request, 'gui/node/storages.html', context)


@login_required
@staff_required
@ajax_required
@require_POST
def storage_form(request, hostname):
    """
    Ajax page for creating or updating compute node storage.
    """
    node = get_node(request, hostname)

    if request.POST['action'] == 'create':
        ns = None
    else:
        try:
            ns = NodeStorage.objects.get(node=node, zpool=request.POST['zpool'])
        except NodeStorage.DoesNotExist:
            raise Http404

    form = NodeStorageForm(request, node, ns, request.POST)

    if form.is_valid():
        status = form.save(args=(hostname, form.cleaned_data.get('zpool')))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('node_storages', hostname)

    return render(request, 'gui/node/storage_form.html', {'node': node, 'form': form})


@login_required
@staff_required
def images(request, hostname):
    """
    Redirect to list of images on default node storage.
    """
    node = get_node(request, hostname)
    nss = node.nodestorage_set.all().values_list('zpool', flat=True).order_by('zpool')

    if nss:
        nz = node.zpool

        if nz and nz in nss:
            zpool_redirect = nz
        elif settings.VMS_STORAGE_DEFAULT in nss:
            zpool_redirect = settings.VMS_STORAGE_DEFAULT
        else:
            zpool_redirect = nss[0]

        return redirect('node_images_zpool', hostname, zpool_redirect)

    context = collect_view_data(request, 'node_list')
    context['nodes'] = Node.all()
    context['node'] = node

    return render(request, 'gui/node/images_disabled.html', context)


@login_required
@staff_required
def images_zpool(request, hostname, zpool):
    """
    List of images on node storages.
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = Node.all()

    try:
        context['ns'] = ns = NodeStorage.objects.select_related('storage').get(node=node, zpool=zpool)
    except NodeStorage.DoesNotExist:
        raise Http404

    context['storages'] = node.nodestorage_set.select_related('storage').all().order_by('zpool').\
        annotate(imgs=Count('images__uuid'))
    context['images'] = ns.images.select_related('owner', 'dc_bound').all().order_by('name').annotate(dcs=Count('dc'))
    image_vms = {}

    for vm in node.vm_set.select_related('dc').all().order_by('hostname'):
        for img_uuid in vm.get_image_uuids(zpool=zpool):
            image_vms.setdefault(img_uuid, []).append({'hostname': vm.hostname, 'dc': vm.dc.name})

    context['image_vms'] = image_vms
    context['form'] = NodeStorageImageForm(ns, initial={'node': hostname, 'zpool': zpool})
    context['last_img'] = request.GET.get('last_img', None)

    return render(request, 'gui/node/images.html', context)


@login_required
@staff_required
def vms(request, hostname, zpool=None):
    """
    List of servers defined on this compute node, optionally filtered by storage (#952).
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = Node.all()
    context['node_online'] = node.is_online()
    context['can_edit'] = True
    context['storages'] = nss = node.nodestorage_set.select_related('storage').all().order_by('zpool')
    all_vms = node.vm_set.select_related('owner', 'dc', 'slavevm', 'slavevm__master_vm').order_by('hostname')
    context['vms_all_count'] = all_vms.count()
    _vms = []

    if zpool and zpool not in {ns.zpool for ns in nss}:
        zpool = None

    for ns in nss:
        ns.vms_count = 0

    for vm in all_vms:
        vm_zpools = vm.get_used_disk_pools()
        vm.resources = vm.get_cpu_ram_disk(zpool=zpool)

        for ns in nss:
            if ns.zpool in vm_zpools:
                ns.vms_count += 1

                if zpool and zpool == ns.zpool:
                    _vms.append(vm)

    if zpool:
        context['vms'] = _vms
    else:
        context['vms'] = all_vms

    context['zpool'] = zpool

    return render(request, 'gui/node/vms.html', context)


# noinspection PyUnusedLocal
def _backup_list_context(request, node, context, vm_hostname=None):
    """Helper of returning list of backups including filters"""
    context['filters'] = filter_form = BackupFilterForm(request, node, request.GET)
    bkps = node.backup_set.select_related('vm', 'dc')
    qs = QueryDict('', mutable=True)

    if filter_form.is_valid() and filter_form.has_changed():
        q = filter_form.get_filters()

        if q:
            qs = request.GET
            bkps = bkps.filter(q)

            if filter_form.vm:
                dc_switch(request, filter_form.vm.dc.name)

    if filter_form.all_vm:
        qs_novm = qs.copy()
        qs_novm.pop('hostname', None)
        context['node_vm_backup_url'] = reverse('node_backups', node.hostname, query_string=qs_novm)
    else:
        qs_nopage = qs.copy()
        qs_nopage.pop('page', None)
        context['qs_nopage'] = qs_nopage.urlencode()

    context['qs'] = qs
    context['vm'] = filter_form.vm
    context['no_vm'] = filter_form.no_vm
    context.update(get_node_backups(request, bkps))

    return context


@login_required
@staff_required
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def backup_definitions(request, hostname):
    """
    List of server backup definitions targeted onto this node.
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = Node.all()
    context['bkpdefs'] = get_node_bkpdefs(node)

    return render(request, 'gui/node/backup_definitions.html', context)


@login_required
@staff_required
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def backups(request, hostname):
    """
    List of server backups stored on this node.
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = (node,)
    context['node_online'] = node.is_online()
    context['submenu_auto'] = ''
    context['lastbkp'] = []
    context['can_edit'] = True
    context['bkp_node'] = True
    context['last_bkpid'] = request.GET.get('last_bkpid', None)

    # This could change the current DC
    _backup_list_context(request, node, context)

    context['bkpform_update'] = UpdateBackupForm(None, prefix='snap_update')
    context['bkpform_restore'] = RestoreBackupForm(get_vms(request, sr=(), prefetch_tags=False))
    context['update_mod_source'] = reverse('node_backup_form', node.hostname, query_string=context['qs'])

    return render(request, 'gui/node/backups.html', context)


@login_required
@staff_required
@ajax_required
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def backup_list(request, hostname, vm_hostname=None):
    """
    Ajax page with list of backups.
    """
    context = {
        'can_edit': True,
        'lastbkp': [],
        'last_bkpid': request.GET.get('last_snapid', None),
    }
    context['node'] = node = get_node(request, hostname)
    _backup_list_context(request, node, context, vm_hostname=vm_hostname)

    if context['vm']:
        template = 'backup_list'
    elif context['no_vm']:
        template = 'backup_list_novm'
    else:
        # This should be never called
        template = 'backup_list_all'

    return render(request, 'gui/node/%s.html' % template, context)


@login_required
@staff_required
@ajax_required
@require_POST
@setting_required('VMS_VM_BACKUP_ENABLED', dc_bound=False)
def backup_form(request, hostname):
    """
    Ajax page for backup form validation when updating backup notes.
    """
    node = get_node(request, hostname)
    bkpform = UpdateBackupForm(None, request.POST, prefix='snap_update')
    status = 200

    if bkpform.is_valid():
        bkp = bkpform.get_backup(node)
        if not bkp:
            raise Http404
        if bkpform.save(bkp):
            status = 201
        else:
            return HttpResponse(None, status=204)  # Nothing changed

    return render(request, 'gui/node/backup_form.html', {'bkpform': bkpform}, status=status)


@login_required
@staff_required
@setting_required('MON_ZABBIX_ENABLED')
def monitoring(request, hostname, graph_type='cpu'):
    """
    Compute node related monitoring.
    """
    dc1_settings = get_dc1_settings(request)
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = Node.all()

    if not dc1_settings.MON_ZABBIX_NODE_SYNC:
        return render(request, 'gui/node/monitoring_disabled.html', context)

    from api.mon.node.graphs import GRAPH_ITEMS

    context['graph_items'] = GRAPH_ITEMS
    context['obj_lifetime'] = node.lifetime
    context['obj_operational'] = node.status != Node.STATUS_AVAILABLE_MONITORING and (
        not graph_type.startswith('vm-') or
        node.vm_set.exclude(status=Vm.NOTCREATED).filter(slavevm__isnull=True).exists()
    )

    if graph_type == 'memory':
        graphs = (
            Graph('mem-usage'),
            Graph('swap-usage')
        )
    elif graph_type == 'network':
        context['node_nics'] = node_nics = node.used_nics.keys()
        graphs = list(chain(*[
            (Graph('net-bandwidth', nic=i), Graph('net-packets', nic=i)) for i in node_nics
        ]))
    elif graph_type == 'storage':
        context['zpools'] = node_zpools = node.zpools
        graphs = list(chain(*[
            (Graph('storage-throughput', zpool=i), Graph('storage-io', zpool=i), Graph('storage-space', zpool=i))
            for i in node_zpools
        ]))
    elif graph_type == 'vm-cpu':
        graphs = (
            Graph('vm-cpu-usage'),
        )
    elif graph_type == 'vm-memory':
        graphs = (
            Graph('vm-mem-usage'),
        )
    elif graph_type == 'vm-disk-throughput':
        graphs = (
            Graph('vm-disk-logical-throughput-reads'),
            Graph('vm-disk-logical-throughput-writes'),
            Graph('vm-disk-physical-throughput-reads'),
            Graph('vm-disk-physical-throughput-writes'),
        )
    elif graph_type == 'vm-disk-io':
        graphs = (
            Graph('vm-disk-logical-io-reads'),
            Graph('vm-disk-logical-io-writes'),
            Graph('vm-disk-physical-io-reads'),
            Graph('vm-disk-physical-io-writes'),
        )
    else:
        graph_type = 'cpu'
        graphs = (
            Graph('cpu-usage'),
            Graph('cpu-jumps'),
            Graph('cpu-load'),
        )

    context['graphs'] = graphs
    context['graph_type'] = graph_type

    return render(request, 'gui/node/monitoring_%s.html' % graph_type, context)


@login_required
@staff_required
def tasklog(request, hostname):
    """
    Compute node related tasklog.
    """
    context = collect_view_data(request, 'node_list')
    context['node'] = node = get_node(request, hostname)
    context['nodes'] = (node,)
    context['submenu_auto'] = ''
    nss = node.nodestorage_set.all().extra(select={'strid': 'CAST(id AS text)'}).values_list('strid', flat=True)
    log_query = ((Q(content_type=ContentType.objects.get_for_model(node)) & Q(object_pk=node.pk)) |
                 (Q(content_type=ContentType.objects.get_for_model(NodeStorage)) & Q(object_pk__in=nss)))
    log = get_tasklog(request, context=context, base_query=log_query, filter_by_permissions=False)
    context['tasklog'] = context['pager'] = tasklog_items = get_pager(request, log, per_page=100)
    TaskLogEntry.prepare_queryset(tasklog_items)

    return render(request, 'gui/node/tasklog.html', context)
