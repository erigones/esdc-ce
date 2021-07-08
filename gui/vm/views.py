from logging import getLogger
from itertools import chain

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST

from gui.vm.guacamole import GuacamoleAuth
from gui.vm.imports import handle_uploaded_file, ImportException
from gui.vm.exports import generate_sample_file, generate_vms_file
from gui.vm.forms import (
    UploadFileForm, PTRForm, ServerSettingsForm, AdminServerSettingsForm, UndoSettingsForm, ServerDiskSettingsForm,
    AdminServerDiskSettingsForm, ServerNicSettingsForm, AdminServerNicSettingsForm, CreateSnapshotForm,
    UpdateSnapshotForm, CreateSnapshotDefineForm, UpdateSnapshotDefineForm, CreateBackupForm, UpdateBackupForm,
    CreateBackupDefineForm, UpdateBackupDefineForm, RestoreBackupForm, SnapshotImageForm
)
from gui.vm.utils import (
    get_vm, get_vms, get_vm_snapshots, get_vm_define_disk, get_vm_define_nic, get_vms_tags, get_vm_snapdefs,
    get_vm_backups, get_vm_bkpdefs, vm_define_all, ImportExportBase, get_ptr_domain_by_ip
)
from gui.decorators import ajax_required, profile_required, admin_required, permission_required
from gui.fields import SIZE_FIELD_MB_ADDON, SIZE_FIELD_PERCENT_ADDON
from gui.utils import collect_view_data, get_pager
from gui.signals import (view_vm_details, view_vm_snapshot, view_vm_backup, view_vm_console, view_vm_monitoring,
                         view_vm_tasklog)
from gui.tasklog.utils import get_tasklog
from gui.models.permission import ImageAdminPermission

from api.decorators import setting_required
from api.response import JSONResponse
from api.vm.utils import get_iso_images
from api.mon.utils import MonitoringGraph as Graph
from api.dns.record.api_views import RecordView

from vms.models import Vm, Node, Image, BackupDefine, DefaultDc

logger = getLogger(__name__)


@login_required
@profile_required
def my_list(request):
    """
    Page with list of all servers that were created by user.
    """
    context = collect_view_data(request, 'vm_list')
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['can_edit'] = request.user.is_admin(request)
    context['vms_node_online'] = not Vm.objects.filter(dc=request.dc, node__isnull=False)\
                                               .exclude(node__status=Node.ONLINE)\
                                               .exists()
    context['stop_timeout_period'] = request.dc.settings.VMS_VM_STOP_TIMEOUT_DEFAULT

    return render(request, 'gui/vm/list.html', context)


@login_required
@profile_required
def details(request, hostname):
    """
    Page with details of server.
    """
    dc_settings = request.dc.settings
    context = collect_view_data(request, 'vm_list', mb_addon=SIZE_FIELD_MB_ADDON)
    context['percent_addon'] = SIZE_FIELD_PERCENT_ADDON
    context['vm'] = vm = get_vm(request, hostname, sr=('dc', 'owner', 'node', 'template', 'slavevm'))
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['vm_disks'] = vm_disks = get_vm_define_disk(request, vm)
    context['vm_nics'] = vm_nics = get_vm_define_nic(request, vm)
    context['ptrform'] = PTRForm(prefix='ptr')
    context['iso_rescuecd'] = dc_settings.VMS_ISO_RESCUECD
    context['mon_sla_enabled'] = (settings.MON_ZABBIX_ENABLED and DefaultDc().settings.MON_ZABBIX_ENABLED and
                                  dc_settings.MON_ZABBIX_VM_SLA)
    context['can_edit'] = request.user.is_admin(request)

    if vm.slave_vms:
        context['slave_vm'] = vm.slave_vm.select_related('master_vm', 'vm', 'vm__node').exclude(name='').first()
    else:
        context['slave_vm'] = None

    if vm.is_hvm():
        context['iso_images'] = get_iso_images(request, vm.ostype)

    if vm.ostype == Vm.WINDOWS:
        context['stop_timeout_period'] = dc_settings.VMS_VM_STOP_WIN_TIMEOUT_DEFAULT
    else:
        context['stop_timeout_period'] = dc_settings.VMS_VM_STOP_TIMEOUT_DEFAULT

    if context['can_edit']:
        context['settingsform'] = AdminServerSettingsForm(request, vm, prefix='opt')

        initial_disk = {
            'disk_id': len(vm_disks) + 1,
            'zpool': vm.zpool,
            'model': dc_settings.VMS_DISK_MODEL_KVM_DEFAULT,
            'compression': dc_settings.VMS_DISK_COMPRESSION_DEFAULT,
            'image': dc_settings.VMS_DISK_IMAGE_DEFAULT,
        }
        if initial_disk['disk_id'] == 1:
            initial_disk['boot'] = True

        initial_nic = {
            'nic_id': len(vm_nics) + 1,
            'model': dc_settings.VMS_NIC_MODEL_DEFAULT,
            'net': dc_settings.VMS_NET_DEFAULT,
        }

        if initial_nic['nic_id'] == 1:
            initial_nic['dns'] = True
            initial_nic['primary'] = True

        if initial_nic['nic_id'] == dc_settings.VMS_NIC_MONITORING_DEFAULT:
            initial_nic['monitoring'] = True

        if vm.template:
            initial_disk.update(vm.template.get_vm_define_disk(initial_disk['disk_id']))
            initial_nic.update(vm.template.get_vm_define_nic(initial_nic['nic_id']))

        context['disk_settingsform'] = AdminServerDiskSettingsForm(request, vm, prefix='opt-disk', initial=initial_disk)
        context['nic_settingsform'] = AdminServerNicSettingsForm(request, vm, prefix='opt-nic', initial=initial_nic)

    else:
        context['settingsform'] = ServerSettingsForm(request, vm, prefix='opt')
        context['disk_settingsform'] = ServerDiskSettingsForm(request, vm, prefix='opt-disk')
        context['nic_settingsform'] = ServerNicSettingsForm(request, vm, prefix='opt-nic')

    view_vm_details.send(sender='gui.vm.views.details', request=request, context=context)
    return render(request, 'gui/vm/details.html', context)


@login_required
@profile_required
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def snapshot(request, hostname):
    """
    Snapshot list and snapshot definitions.
    """
    context = collect_view_data(request, 'vm_list')
    context['vm'] = vm = get_vm(request, hostname, sr=('dc', 'owner', 'template', 'slavevm'))
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['can_edit'] = request.user.is_admin(request)
    context['can_image'] = request.user.is_staff or request.user.has_permission(request, ImageAdminPermission.name)
    context['cannot_snapshot'] = not (request.user.is_admin(request) or vm.is_installed())
    context['snapform_create'] = CreateSnapshotForm(vm, prefix='snap_create', initial={'disk_id': 1})
    context['snapform_update'] = UpdateSnapshotForm(vm, prefix='snap_update')
    context['lastsnap'] = []
    context['snapdefs'] = get_vm_snapdefs(vm)
    context.update(get_vm_snapshots(request, vm))  # Add snapshots and count attributes + paginator

    if context['can_edit']:
        context['snapdeform_update'] = UpdateSnapshotDefineForm(request, vm)
        context['snapdeform_create'] = CreateSnapshotDefineForm(request, vm, prefix='snapdef_create',
                                                                initial={'disk_id': 1, 'active': True})
        context['bkpform_restore'] = RestoreBackupForm(vms)

    if context['can_image']:
        context['imgform'] = SnapshotImageForm(vm, request, None, prefix='img', initial={'owner': request.user.username,
                                                                                         'access': Image.PRIVATE,
                                                                                         'version': '1.0'})

    view_vm_snapshot.send(sender='gui.vm.views.snapshot', request=request, context=context)
    return render(request, 'gui/vm/snapshot.html', context)


@login_required
@profile_required
@setting_required('VMS_VM_BACKUP_ENABLED')
def backup(request, hostname):
    """
    Backup list and backup definitions.
    """
    dc_settings = request.dc.settings
    context = collect_view_data(request, 'vm_list')
    context['vm'] = vm = get_vm(request, hostname, sr=('dc', 'owner', 'template', 'slavevm'))
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['can_edit'] = request.user.is_admin(request)
    context['bkpdefs'] = bkpdefs = get_vm_bkpdefs(vm)
    context['lastbkp'] = []
    context.update(get_vm_backups(request, vm))  # Add paginator

    if context['can_edit']:
        context['bkpform_create'] = CreateBackupForm(vm, bkpdefs, prefix='snap_create')
        context['bkpform_restore'] = RestoreBackupForm(vms)
        context['bkpform_update'] = UpdateBackupForm(vm, prefix='snap_update')
        context['bkpdeform_update'] = UpdateBackupDefineForm(request, vm)
        bkpdef_initial = {
            'zpool': dc_settings.VMS_STORAGE_DEFAULT,
            'type': BackupDefine.DATASET,
            'disk_id': 1,
            'active': True,
            'compression': dc_settings.VMS_VM_BACKUP_COMPRESSION_DEFAULT
        }
        context['bkpdeform_create'] = CreateBackupDefineForm(request, vm, prefix='bkpdef_create',
                                                             initial=bkpdef_initial)

    view_vm_backup.send(sender='gui.vm.views.backup', request=request, context=context)
    return render(request, 'gui/vm/backup.html', context)


@login_required
@profile_required
def console(request, hostname):
    """
    Page with remote VNC console of the server.
    """
    context = collect_view_data(request, 'vm_list')
    context['vm'] = get_vm(request, hostname)
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['can_edit'] = request.user.is_admin(request)

    view_vm_console.send(sender='gui.vm.views.console', request=request, context=context)
    return render(request, 'gui/vm/console.html', context)


@login_required
@profile_required
@setting_required('MON_ZABBIX_ENABLED', default_dc=True)
def monitoring(request, hostname, graph_type='cpu'):
    """
    Page with monitoring graphs.
    """
    context = collect_view_data(request, 'vm_list')
    context['vm'] = vm = get_vm(request, hostname)
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)
    context['can_edit'] = request.user.is_admin(request)

    if vm.is_notcreated():
        zabbix_sync_enabled = vm.zabbix_sync
    else:
        zabbix_sync_enabled = vm.is_zabbix_sync_active()

    if not zabbix_sync_enabled:
        return render(request, 'gui/vm/monitoring_disabled.html', context)

    from api.mon.vm.graphs import GRAPH_ITEMS

    context['graph_items'] = GRAPH_ITEMS
    context['obj_lifetime'] = vm.lifetime
    context['obj_operational'] = vm.status in vm.STATUS_OPERATIONAL

    if graph_type == 'memory':
        graphs = (
            Graph('mem-usage'),
            Graph('swap-usage'),
        )
    elif graph_type == 'network':
        context['vm_nics'] = nics = range(1, len(vm.json_get_nics()) + 1)
        graphs = list(chain(*[
            (Graph('net-bandwidth', nic_id=i), Graph('net-packets', nic_id=i)) for i in nics
        ]))
    elif graph_type == 'disk':
        if vm.is_hvm():
            prefix = 'disk'
        else:
            prefix = 'fs'

        context['desc_throughput'] = GRAPH_ITEMS.get(prefix + '-throughput').get('desc')
        context['desc_io'] = GRAPH_ITEMS.get(prefix + '-io').get('desc')
        context['graph_prefix'] = prefix
        context['vm_disks'] = disks = range(1, len(vm.json_get_disks()) + 1)
        graphs = list(chain(*[
            (Graph(prefix + '-throughput', disk_id=i), Graph(prefix + '-io', disk_id=i)) for i in disks
        ]))
    elif graph_type == 'vm-disk':
        graphs = (
            Graph('vm-disk-logical-throughput'),
            Graph('vm-disk-logical-io'),
            Graph('vm-disk-physical-throughput'),
            Graph('vm-disk-physical-io'),
            Graph('vm-disk-io-operations'),
        )
    else:
        graph_type = 'cpu'
        graphs = (
            Graph('cpu-usage'),
            Graph('cpu-waittime'),
            Graph('cpu-load'),
        )

    context['graphs'] = graphs
    context['graph_type'] = graph_type

    view_vm_monitoring.send(sender='gui.vm.views.monitoring', request=request, context=context)
    return render(request, 'gui/vm/monitoring_%s.html' % graph_type, context)


@login_required
@profile_required
def tasklog(request, hostname):
    """
    Page with server related tasklog.
    """
    context = collect_view_data(request, 'vm_list')
    context['vm'] = vm = get_vm(request, hostname)
    context['vms'] = (vm,)
    context['submenu_auto'] = ''
    context['vms_tag_filter_disabled'] = True
    log_query = Q(content_type=vm.get_content_type()) & Q(object_pk=vm.pk)
    log = get_tasklog(request, context, base_query=log_query)
    context['tasklog'] = context['pager'] = get_pager(request, log, per_page=100)
    context['can_edit'] = request.user.is_admin(request)

    view_vm_tasklog.send(sender='gui.vm.views.tasklog', request=request, context=context)
    return render(request, 'gui/vm/tasklog.html', context)


@login_required
@ajax_required
@require_POST
def set_installed(request, hostname):
    """
    Ajax page for marking the server as installed.
    """
    vm = get_vm(request, hostname)

    if request.POST.get('installed'):
        # PUT vm_define
        res = ServerSettingsForm.api_call('update', vm, request, args=(hostname,), data={'installed': True})
        if res.status_code == 200:
            messages.success(request, _('Server was marked as installed.'))
            return redirect(request.build_absolute_uri(reverse('vm_details', kwargs={'hostname': hostname})))
        else:
            return JSONResponse(res.data, status=res.status_code)

    raise PermissionDenied


@login_required
@ajax_required
@require_POST
@setting_required('DNS_ENABLED')
def ptr_form(request, hostname, nic_id):
    """
    Ajax page for PTR form validation.
    """
    vm = get_vm(request, hostname)

    try:
        nic = vm.json_get_nics()[int(nic_id) - 1]
        nic_ip = nic['ip']
        ptr_domain = get_ptr_domain_by_ip(vm, nic_ip)
        ptr = RecordView.Record.get_record_PTR(nic_ip, ptr_domain)
        if not ptr:
            raise Exception('PTR Record not found')
    except Exception:
        raise Http404

    ptrform = PTRForm(request.POST, prefix='ptr')

    if ptrform.is_valid():
        if ptrform.cleaned_data['content'] == ptr.content:
            return HttpResponse(None, status=204)
        else:
            res = RecordView.internal_response(request, 'PUT', ptr, ptrform.cleaned_data, related_obj=vm)

            if res.status_code in (200, 201):
                return HttpResponse(None, status=201)
            else:
                ptrform.set_api_errors(res.data)

    return render(request, 'gui/vm/ptr_form.html', {'ptrform': ptrform})


@login_required
@admin_required
@ajax_required
@require_POST
def add_import_form(request):
    """
    Ajax page for importing new servers.
    """
    form = UploadFileForm(request.POST, request.FILES)

    if not form.is_valid():
        return render(request, 'gui/vm/import_form.html', {'importform': form})

    # Get data from xls file
    html_table = None
    defined_vms = {}
    import_error = None
    filename = form.cleaned_data.get('import_file')

    try:
        html_table = handle_uploaded_file(filename, request)
    except ImportException as e:
        import_error = e.message
        logger.warning('Could not import file %s: %s', filename, e.message)
    except Exception as e:
        import_error = _('Import Failed')
        logger.exception(e)
    else:
        redirect_to_vm_list = True

        for vm in html_table:
            status, html_table[vm] = vm_define_all(request, html_table[vm])
            if status == 201:
                defined_vms[vm] = html_table[vm]
            else:
                redirect_to_vm_list = False

                if html_table[vm]['_vm_defined']:
                    defined_vms[vm] = html_table[vm]

        if redirect_to_vm_list:
            return redirect(request.build_absolute_uri(reverse('vm_list')))

        # Some server creation has failed, remove all created server definitions
        for vm in defined_vms:
            status, defined_vms[vm] = vm_define_all(request, defined_vms[vm], method='DELETE')

    ieb = ImportExportBase()

    return render(request, 'gui/vm/add_import.html', {
        'importform': form,  # TODO: needed?
        'filename': filename,
        'header': ieb.get_file_header(),
        'vms': html_table,
        'import_error': import_error,
    }, status=281)


@login_required
@ajax_required
def add_settings_form(request):
    """
    Ajax page for adding new server.
    """
    if request.user.is_admin(request):  # must check can_edit permission
        return settings_form(request, None)

    raise PermissionDenied


@login_required
@ajax_required
@require_POST
def settings_form(request, hostname):
    """
    Ajax page for changing server settings.
    """
    if hostname is None:
        vm = None
    else:
        vm = get_vm(request, hostname)

    if request.user.is_admin(request):  # can_edit permission
        action = None
        form = AdminServerSettingsForm(request, vm, request.POST, prefix='opt')
    else:
        action = 'update'
        form = ServerSettingsForm(request, vm, request.POST, prefix='opt')

    # noinspection PyUnresolvedReferences
    if form.is_valid():
        # noinspection PyUnresolvedReferences
        status = form.save(action=action, args=(form.current_hostname,))
        if status == 204:
            # Nothing changed
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            # noinspection PyUnresolvedReferences
            if form.action == 'delete':
                return redirect(request.build_absolute_uri(reverse('vm_list')))
            else:
                return redirect(
                    request.build_absolute_uri(reverse('vm_details', kwargs={'hostname': form.saved_hostname}))
                )

    return render(request, 'gui/vm/settings_form.html', {
        'settingsform': form,
        'vm': vm,
        'mb_addon': SIZE_FIELD_MB_ADDON,
        'percent_addon': SIZE_FIELD_PERCENT_ADDON,
    })


@login_required
@ajax_required
@require_POST
def disk_settings_form(request, hostname):
    """
    Ajax page for changing server disk settings.
    """
    vm = get_vm(request, hostname)

    if request.user.is_admin(request):  # can_edit permission
        action = None
        form = AdminServerDiskSettingsForm(request, vm, request.POST, prefix='opt-disk')
    else:
        action = 'update'
        form = ServerDiskSettingsForm(request, vm, request.POST, prefix='opt-disk')

    # noinspection PyUnresolvedReferences
    if form.is_valid():
        # noinspection PyUnresolvedReferences
        status = form.save(action=action, args=(vm.hostname, form.cleaned_data['disk_id']))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect(request.build_absolute_uri(reverse('vm_details', kwargs={'hostname': vm.hostname})))

    return render(request, 'gui/vm/disk_settings_form.html', {
        'disk_settingsform': form,
        'vm': vm,
        'mb_addon': SIZE_FIELD_MB_ADDON,
        'percent_addon': SIZE_FIELD_PERCENT_ADDON,
    })


@login_required
@ajax_required
@require_POST
def nic_settings_form(request, hostname):
    """
    Ajax page for changing server nic settings.
    """
    vm = get_vm(request, hostname)

    if request.user.is_admin(request):  # can_edit permission
        action = None
        form = AdminServerNicSettingsForm(request, vm, request.POST, prefix='opt-nic')
    else:
        action = 'update'
        form = ServerNicSettingsForm(request, vm, request.POST, prefix='opt-nic')

    # noinspection PyUnresolvedReferences
    if form.is_valid():
        # noinspection PyUnresolvedReferences
        status = form.save(action=action, args=(vm.hostname, form.cleaned_data['nic_id']))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect(request.build_absolute_uri(reverse('vm_details', kwargs={'hostname': vm.hostname})))

    return render(request, 'gui/vm/nic_settings_form.html', {'nic_settingsform': form, 'vm': vm})


@login_required
@ajax_required
@require_POST
def undo_settings(request, hostname):
    """
    Ajax page for reverting server definition by calling vm_define_revert.
    """
    vm = get_vm(request, hostname)
    res = UndoSettingsForm.api_call('update', vm, request, args=(hostname,))

    if res.status_code == 200:
        return redirect(request.build_absolute_uri(reverse('vm_details', kwargs={'hostname': vm.hostname})))

    return JSONResponse(res.data, status=res.status_code)


@login_required
@ajax_required
@require_POST
def multi_settings_form(request):
    """
    Ajax page for changing settings of multiple servers.
    """
    if not request.user.is_admin(request):  # can_edit permission
        raise PermissionDenied

    if request.POST['action'] == 'delete':  # delete only for now
        for hostname in request.POST.getlist('hostname'):
            # DELETE vm_define
            vm = get_vm(request, hostname, auto_dc_switch=False)
            res = AdminServerSettingsForm.api_call('delete', vm, request, args=(hostname,))
            if res.status_code != 200:
                return JSONResponse(res.data, status=res.status_code)

        node = request.GET.get('node', None)

        if node:
            return redirect(request.build_absolute_uri(reverse('node_vms', args=node)))
        else:
            return redirect(request.build_absolute_uri(reverse('vm_list')))


@login_required
@ajax_required
@require_POST
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def snapshot_form(request, hostname):
    """
    Ajax page for snapshot form validation when creating or updating snapshot.
    """
    vm = get_vm(request, hostname)
    status = 200

    if request.POST.get('update', None):
        snapform = UpdateSnapshotForm(vm, request.POST, prefix='snap_update')
        if snapform.is_valid():
            snap = snapform.get_snapshot()
            if not snap:
                raise Http404
            if snapform.save(snap):
                status = 201
            else:
                return HttpResponse(None, status=204)  # Nothing changed
    else:
        snapform = CreateSnapshotForm(vm, request.POST, prefix='snap_create')
        if snapform.is_valid():
            status = 201

    context = {'snapform': snapform, 'vm': vm}

    return render(request, 'gui/vm/snapshot_form.html', context, status=status)


@login_required
@ajax_required
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def snapshot_list(request, hostname):
    """
    Ajax page with list of snapshots.
    """
    vm = get_vm(request, hostname)
    context = {
        'vm': vm,
        'can_edit': request.user.is_admin(request),
        'lastsnap': [],
        'last_snapid': request.GET.get('last_snapid', None),
    }
    context.update(get_vm_snapshots(request, vm))  # Add snapshots and count attributes + paginator

    return render(request, 'gui/vm/snapshot_list.html', context)


@login_required
@admin_required  # can_edit
@ajax_required
@require_POST
@setting_required('VMS_VM_BACKUP_ENABLED')
def backup_form(request, hostname):
    """
    Ajax page for backup form validation when creating or updating backup.
    """
    vm = get_vm(request, hostname)
    status = 200

    if request.POST.get('update', None):
        template = 'backup_form_update.html'
        bkpform = UpdateBackupForm(vm, request.POST, prefix='snap_update')

        if bkpform.is_valid():
            bkp = bkpform.get_backup()
            if not bkp:
                raise Http404
            if bkpform.save(bkp):
                status = 201
            else:
                return HttpResponse(None, status=204)  # Nothing changed

    else:
        template = 'backup_form.html'
        bkpform = CreateBackupForm(vm, get_vm_bkpdefs(vm), request.POST, prefix='snap_create')
        if bkpform.is_valid():
            status = 201

    context = {'bkpform': bkpform, 'vm': vm}

    return render(request, 'gui/vm/' + template, context, status=status)


@login_required
@ajax_required
@setting_required('VMS_VM_BACKUP_ENABLED')
def backup_list(request, hostname):
    """
    Ajax page with list of backups.
    """
    vm = get_vm(request, hostname)
    context = {
        'vm': vm,
        'can_edit': request.user.is_admin(request),
        'lastbkp': [],
        'last_bkpid': request.GET.get('last_snapid', None),
        'bkpdefs': True,  # Always enable "backup now" button
    }
    context.update(get_vm_backups(request, vm))  # Add paginator

    return render(request, 'gui/vm/backup_list.html', context)


@login_required
@admin_required  # can_edit
@ajax_required
@require_POST
@setting_required('VMS_VM_SNAPSHOT_ENABLED')
def snapshot_define_form(request, hostname):
    """
    Ajax page for snapshot define settings.
    """
    vm = get_vm(request, hostname)

    if request.POST.get('action', None) == 'create':
        form = CreateSnapshotDefineForm(request, vm, request.POST, prefix='snapdef_create')
    else:
        form = UpdateSnapshotDefineForm(request, vm, request.POST)

    if form.is_valid():
        # noinspection PyUnresolvedReferences
        status = form.save(args=(vm.hostname, form.cleaned_data['name']))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('vm_snapshot', hostname=vm.hostname)

    return render(request, 'gui/vm/snapshot_define_form.html', {'form': form, 'vm': vm})


@login_required
@admin_required  # can_edit
@ajax_required
@require_POST
@setting_required('VMS_VM_BACKUP_ENABLED')
def backup_define_form(request, hostname):
    """
    Ajax page for backup define settings.
    """
    vm = get_vm(request, hostname)

    if request.POST.get('action', None) == 'create':
        form = CreateBackupDefineForm(request, vm, request.POST, prefix='bkpdef_create')
    else:
        form = UpdateBackupDefineForm(request, vm, request.POST)

    if form.is_valid():
        # noinspection PyUnresolvedReferences
        status = form.save(args=(vm.hostname, form.cleaned_data['name']))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('vm_backup', hostname=vm.hostname)

    return render(request, 'gui/vm/backup_define_form.html', {'form': form, 'vm': vm})


@login_required
@admin_required  # SuperAdmin or DCAdmin+ImageAdmin
@permission_required(ImageAdminPermission)
@ajax_required
@require_POST
def snapshot_image_form(request, hostname):
    """
    Ajax page for creating new image from server snapshot.
    """
    vm = get_vm(request, hostname)

    form = SnapshotImageForm(vm, request, None, request.POST, prefix='img')

    if form.is_valid():
        status = form.save(args=(vm.hostname, form.cleaned_data['snapname'], form.cleaned_data['name']))
        if status == 204:
            return HttpResponse(None, status=status)
        elif status in (200, 201):
            return redirect('vm_snapshot', hostname=vm.hostname)

    return render(request, 'gui/vm/image_snapshot_form.html', {'form': form, 'vm': vm})


def _generic_add_context(request):
    """
    Collect generic context for add vm view.

    Partial add VM view, was separated to smaller functions due to code reuse in Enterprise Edition apps (payments).
    """
    context = collect_view_data(request, 'vm_add', mb_addon=SIZE_FIELD_MB_ADDON, percent_addon=SIZE_FIELD_PERCENT_ADDON)
    context['vms'] = vms = get_vms(request)
    context['vms_tags'] = get_vms_tags(vms)

    return context


def _render_admin_add(request, context):
    """
    Render add vm view for admin (user with can_edit permission).

    Partial add VM view, was separated to smaller functions due to code reuse in Enterprise Edition apps (payments).
    """
    dc_settings = request.dc.settings

    initial = dc_settings.VMS_VM_JSON_DEFAULTS['internal_metadata'].copy()
    initial['node'] = request.GET.get('node', None)
    initial['domain'] = dc_settings.VMS_VM_DOMAIN_DEFAULT
    initial['monitored'] = dc_settings.MON_ZABBIX_ENABLED and dc_settings.MON_ZABBIX_VM_SYNC \
        and dc_settings.VMS_VM_MONITORED_DEFAULT
    initial['cpu_shares'] = dc_settings.VMS_VM_CPU_SHARES_DEFAULT
    initial['zfs_io_priority'] = dc_settings.VMS_VM_ZFS_IO_PRIORITY_DEFAULT
    initial['zpool'] = dc_settings.VMS_STORAGE_DEFAULT
    initial['ostype'] = dc_settings.VMS_VM_OSTYPE_DEFAULT
    initial['hvm_type'] = dc_settings.VMS_VM_HVM_TYPE_DEFAULT
    initial['snapshot_limit_manual'] = dc_settings.VMS_VM_SNAPSHOT_LIMIT_MANUAL_DEFAULT
    initial['snapshot_size_percent_limit'] = dc_settings.VMS_VM_SNAPSHOT_SIZE_PERCENT_LIMIT_DEFAULT
    initial['snapshot_size_limit'] = dc_settings.VMS_VM_SNAPSHOT_SIZE_LIMIT_DEFAULT
    initial['bootrom'] = dc_settings.VMS_BHYVE_BOOTROM_DEFAULT
    initial['owner'] = request.user.username
    initial['mdata'] = dc_settings.VMS_VM_MDATA_DEFAULT
    context['settingsform'] = AdminServerSettingsForm(request, None, prefix='opt', initial=initial)
    context['importform'] = UploadFileForm()

    return render(request, 'gui/vm/add.html', context)


@login_required
@profile_required
def add(request):
    """
    Add server view.

    View url is overloaded in Enterprise Edition apps (payments) to add extra functionality.
    """
    context = _generic_add_context(request)

    if request.user.is_admin(request):  # can_edit permission
        return _render_admin_add(request, context)

    return render(request, 'gui/vm/add_disabled.html', context)


@login_required
@profile_required
@admin_required
def vm_import_sample(request):
    return generate_sample_file(request)


@login_required
@profile_required
def vm_export(request):
    return generate_vms_file(request, request.GET.getlist('hostname'))


@login_required
@profile_required
def vnc(request, hostname):
    """
    Guacamole remote console view.
    """
    # get VM object or raise 404
    vm = get_vm(request, hostname, sr=('dc', 'owner', 'node'))

    # basic view data
    context = {'vm': vm, 'gc': {}}

    # First check if VNC is available for this vm and vm is running
    if not (vm.status in (vm.RUNNING, vm.STOPPING) and
            vm.node and vm.node.address and vm.vnc_port and vm.node.status in Node.STATUS_OPERATIONAL and
            vm.vnc_port == vm.json_active.get('vnc_port', None)):
        # VNC settings not found or VM is not running
        return render(request, 'gui/vm/vnc.html', context)

    # Test if VNC port is open (e.g. when the VM was just started, but the vnc is not yet initialized)
    if not GuacamoleAuth.test_vnc(vm):
        # VNC port is not open yet, but maybe it will be in few seconds (see the JS in vnc.html)
        context['gc']['ready'] = False
        return render(request, 'gui/vm/vnc.html', context)

    # set Guacamole tunnel setting
    context['gc'] = {
        'ready': True,
        'tunnel': settings.GUACAMOLE_HTU,
        'wss': settings.GUACAMOLE_WSS,
        'vnc_zoom': bool(request.GET.get('zoom', settings.GUACAMOLE_DEFAULT_ZOOM)),
    }

    # return vnc window without login (we already have a JSESSIONID cookie)
    if request.GET.get('nologin', False):
        context['gc']['token'] = request.session.get(settings.GUACAMOLE_TOKEN, '')
        return render(request, 'gui/vm/vnc.html', context)

    # Create guacamole object attached to request.user.username and VM
    # A password for the user will be generated automatically
    g = GuacamoleAuth(request, vm)
    # Create a VM usermap for this request.user and VM and set guacamole configuration into cache
    g.set_auth()
    # Perform a login to guacamole, which will give you a JSESSIONID cookie.
    gcookie = g.login()
    context['gc']['token'] = gcookie.get('token', '')
    # Get a response object
    response = render(request, 'gui/vm/vnc.html', context)
    # Set the guacamole cookie into the response object
    if 'cookie' in gcookie:
        response.set_cookie(**gcookie['cookie'])
    # Delete usermap (it is cached in guacamole)
    g.del_auth()

    # Give it to the user
    return response
