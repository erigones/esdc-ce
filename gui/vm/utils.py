from django.http import Http404
from django.utils.translation import ugettext_lazy as _
from django.utils.six import iteritems

from logging import getLogger
import json

from vms.models import Vm, Image, SnapshotDefine, Snapshot, BackupDefine, Backup, TagVm
from gui.utils import get_order_by, get_pager
from gui.exceptions import HttpRedirectException
from gui.dc.views import dc_switch
from api.vm.utils import get_vms as api_get_vms, get_vm as api_get_vm
from api.vm.define.serializers import VmDefineSerializer, VmDefineDiskSerializer, VmDefineNicSerializer
from api.vm.define.views import vm_define, vm_define_nic, vm_define_disk
from api.vm.snapshot.vm_snapshot_list import VmSnapshotList
from api.vm.backup.vm_backup_list import VmBackupList
from api.utils.views import call_api_view

logger = getLogger(__name__)


def get_vm(request, hostname, exists_ok=True, noexists_fail=True, auto_dc_switch=True, sr=('dc', 'owner')):
    """
    Get VM object or raise 404.
    """
    if auto_dc_switch:
        try:
            vm = Vm.objects.filter(slavevm__isnull=True).select_related(*sr).get(hostname=hostname)
        except Vm.DoesNotExist:
            raise Http404
        else:
            if vm.dc != request.dc:
                # Switch to VM's DC -> will return False if user is not allowed to switch to DC
                if dc_switch(request, vm.dc.name):
                    raise HttpRedirectException(request.path)
                else:
                    raise Http404

        if request.user.is_admin(request) or vm.owner == request.user:
            return vm

    try:
        return api_get_vm(request, hostname, exists_ok=exists_ok, noexists_fail=noexists_fail, api=False,
                          sr=sr, check_node_status=None)
    except Vm.DoesNotExist:
        raise Http404


def get_vm_snapshots(request, vm):
    """
    Return list of all snapshots and counts.
    """
    user_order_by, order_by = get_order_by(request, api_view=VmSnapshotList,
                                           db_default=('-id',), user_default=('-created',))
    snapshots = get_pager(request, Snapshot.objects.select_related('vm', 'define').filter(vm=vm).order_by(*order_by),
                          per_page=50)

    return {
        'order_by': user_order_by,
        'pager': snapshots,
        'snapshots': snapshots,
        'snapshots_count': snapshots.paginator.count,
        'snapshots_count_manual': Snapshot.objects.filter(vm=vm, type=Snapshot.MANUAL).count(),  # TODO: check indexes
        'snapshots_count_auto': Snapshot.objects.filter(vm=vm, type=Snapshot.AUTO).count(),
    }


def get_vm_backups(request, vm):
    """
    Return QuerySet of all VM backups.
    """
    user_order_by, order_by = get_order_by(request, api_view=VmBackupList,
                                           db_default=('-id',), user_default=('-created',))
    bkps = get_pager(request, Backup.objects.select_related('node', 'vm', 'define').filter(vm=vm).order_by(*order_by),
                     per_page=50)

    return {
        'order_by': user_order_by,
        'pager': bkps,
        'backups': bkps,
        'backups_count': bkps.paginator.count,
    }


def get_vm_snapdefs(vm, sr=('vm', 'periodic_task', 'periodic_task__crontab')):
    """
    Return QuerySet of all VM snapshot definitions.
    """
    if vm.is_notcreated() and vm.template:
        qs = vm.template.vm_define_snapshot_web_data
    else:
        qs = SnapshotDefine.objects.select_related(*sr).filter(vm=vm).order_by('-id')
        setattr(qs, 'definition', False)

    return qs


def get_vm_bkpdefs(vm, sr=('vm', 'node', 'periodic_task', 'periodic_task__crontab')):
    """
    Return QuerySet of all VM snapshot definitions.
    """
    if vm.is_notcreated() and vm.template:
        qs = vm.template.vm_define_backup_web_data
    else:
        qs = BackupDefine.objects.select_related(*sr).filter(vm=vm).order_by('-id')
        setattr(qs, 'definition', False)

    return qs


def get_vms(request, sr=('node', 'owner'), prefetch_tags=True):
    """
    Return user/admin VMs.
    """
    qs = api_get_vms(request, sr=sr)

    if prefetch_tags:
        return qs.prefetch_related('tags')

    return qs


def get_custom_images():
    """
    Return list of custom images used in vm-buy.
    """
    return [i for i in Image.CUSTOM.values() if i.access == Image.PUBLIC]


def get_vm_define(request, vm, many=False):
    """
    Like GET api.vm.define.vm_define.
    """
    request.method = 'GET'

    if many:
        return VmDefineSerializer(request, vm, many=True).data

    return VmDefineSerializer(request, vm).data


def get_vm_define_disk(request, vm, disk_id=None):
    """
    Like GET api.vm.define.vm_define_disk_list.
    """
    request.method = 'GET'

    if disk_id is not None:
        return VmDefineDiskSerializer(request, vm, vm.json_get_disks()[disk_id], disk_id=disk_id).data

    return VmDefineDiskSerializer(request, vm, vm.json_get_disks(), many=True).data


def get_vm_define_nic(request, vm, nic_id=None):
    """
    Like GET api.vm.define.vm_define_nic_list.
    """
    request.method = 'GET'

    if nic_id is not None:
        return VmDefineNicSerializer(request, vm, vm.json_get_nics()[nic_id], nic_id=nic_id).data

    return VmDefineNicSerializer(request, vm, vm.json_get_nics(), many=True).data


def get_vms_tags(vms):
    """
    Return tag queryset only for vms queryset.
    """
    return list(TagVm.objects.distinct().filter(content_object__in=vms).order_by('tag__name').values_list('tag__name',
                                                                                                          'tag__id'))


def format_error(msg):
    if isinstance(msg, list):
        if len(msg) > 1:
            return ", ".join(msg)
        else:
            return msg[0]
    return msg


def process_errors(data, vm_details, row_no):
    """
    Common api error parser like in SerializerForm._set_api_errors()
    """
    errors = data.get('result', data)
    if errors:
        if 'non_field_errors' in errors:
            header_type = 'hostname'
            if errors['non_field_errors'] == ['Cannot find free IP address for net testlan.']:
                header_type = 'ip'
            vm_details['html_rows'][row_no]['errors'][header_type] = format_error(errors['non_field_errors'])
        elif 'detail' in errors:
            vm_details['html_rows'][row_no]['errors']['hostname'] = format_error(errors['detail'])
        else:
            ieb = ImportExportBase()
            for header_type, error_message in iteritems(errors):
                header_type = ieb.convert_header_to_file_header(header_type)
                vm_details['html_rows'][row_no]['errors'][header_type] = format_error(error_message)
    return vm_details


def vm_define_all(request, vm_details, method='POST'):
    """
    Run all API functions to define VM we run vm_define, vm_define_disk a vm_define_nic,
    it also supports to pass request method DELETE to remove server.
    Return status_code and vm_details
    """
    ieb = ImportExportBase()

    vm, nics, disks = ieb.prepare_vm(json.loads(vm_details['json']))
    logger.debug('Extracted json %s', json.loads(vm_details['json']))
    hostname = vm['hostname']
    success = True

    try:  # Set server zpool from first disk pool
        vm['zpool'] = disks[0]['zpool']
    except (IndexError, KeyError):
        pass

    # API: POST vm_define()
    logger.info('Calling API view %s vm_define(%s, data=%s) by user %s in DC %s',
                method, hostname, vm, request.user, request.dc)
    res = call_api_view(request, method, vm_define, hostname, data=vm, disable_throttling=True)

    # when deleting server, system would delete nic and disk automatically
    if method == 'DELETE':
        success = False

    if res.status_code not in (200, 201) and method == 'POST':
        success = False
        logger.warning('vm_define: "%s" status_code: "%s" data: %s', hostname, res.status_code, res.data)
        vm_details = process_errors(res.data, vm_details, 0)

    # Try to create NIC and DISK only if server has been created
    if success:
        nic_id = 1
        html_row_counter = 0
        for nic in nics:
            # API: POST vm_define_nic()
            logger.info('Calling API view vm_define_nic(%s, %s, data=%s) by user %s in DC %s', hostname, nic_id, nic,
                        request.user, request.dc)
            res = call_api_view(request, 'POST', vm_define_nic, hostname, nic_id, data=nic, disable_throttling=True)

            if res.status_code not in (200, 201):
                success = False
                logger.warning('vm_define_nic: "%s" nic_id: "%s" status_code: "%s" data: %s', hostname, nic_id,
                               res.status_code, res.data)
                vm_details = process_errors(res.data, vm_details, html_row_counter)
            else:
                nic_id += 1
            html_row_counter += 1

        disk_id = 1
        html_row_counter = 0
        for i, disk in enumerate(disks):
            # API: POST vm_define_disk()
            logger.info('Calling API view vm_define_disk(%s, %s, data=%s) by user %s in DC %s', hostname, disk_id,
                        disk, request.user, request.dc)

            # disk_id 1 for zone is created automatically we can just update it here...
            if i == 0 and vm['ostype'] in Vm.ZONE:
                res = call_api_view(request, 'PUT', vm_define_disk, hostname, disk_id, data=disk,
                                    disable_throttling=True)
            else:
                res = call_api_view(request, 'POST', vm_define_disk, hostname, disk_id, data=disk,
                                    disable_throttling=True)

            if res.status_code not in (200, 201):
                success = False
                logger.warning('vm_define_disk: "%s" disk_id: "%s" status_code: "%s" data: %s', hostname, disk_id,
                               res.status_code, res.data)
                vm_details = process_errors(res.data, vm_details, html_row_counter)
            else:
                disk_id += 1
            html_row_counter += 1

    if success:
        logger.debug('Server %s has been defined.', hostname)
        return 201, vm_details
    else:
        return 400, vm_details


class ImportExportBase(object):
    # Sheets will be created either in export or in import
    sheet_dc_name = 'Datacenter'
    sheet_dc = None
    sheet_data_name = 'Data'
    sheet_data = None

    # we compare to lower-cased header in file (we don't care about case sensitiveness here)
    from collections import namedtuple
    hm_row = namedtuple('HeaderMapRow', 'column filename keyname')
    HEADER_MAP = (
        hm_row('A', 'Hostname', 'hostname'),
        hm_row('B', 'Alias', 'alias'),
        hm_row('C', 'Tags', 'tags'),
        hm_row('D', 'Node', 'node'),
        hm_row('E', 'OS Type', 'ostype'),
        hm_row('F', 'vCPU', 'vcpus'),
        hm_row('G', 'RAM', 'ram'),
        hm_row('H', 'Network', 'net'),
        hm_row('I', 'IP', 'ip'),
        hm_row('J', 'Storage', 'storage'),
        hm_row('K', 'HDD Size', 'size'),
        hm_row('L', 'Image', 'image'),
        # ('M', 'Backup', 'backup'), # Backup will be part of 2.1 or later....
    )
    HEADER_ERROR = _('Header does not match expected fields!')
    vm_fields = ('hostname', 'alias', 'node', 'tags', 'os type', 'vcpu', 'ram')

    def __init__(self):
        # mutable attributes have to be initialized inside __init__
        self.header = []
        self.file_header = []

    @staticmethod
    def get_letter(number):
        # TODO: Handle negative number
        # TODO: Handle excel way numbers larger than alphabet, eg. 27 == AB not \
        return chr(number + ord('@'))  # We use one before A because get_letter(1) have to return A

    def update_header(self):
        for item in self.HEADER_MAP:
            self.file_header.append(item.filename.lower())
            self.header.append(item.keyname.lower())

    def get_header(self):
        if not self.header:
            self.update_header()
        return self.header

    def get_file_header(self):
        if not self.file_header:
            self.update_header()
        return self.file_header

    def get_column_index(self, value):
        for row in self.HEADER_MAP:
            if value in row:
                return row[0]
        raise ValueError('Could not find %s in HEADER_MAP' % value)

    def convert_header_to_file_header(self, item):
        header = self.get_header()
        file_header = self.get_file_header()
        if item in header:
            return file_header[header.index(item)]
        return None

    def convert_file_header_to_header(self, item):
        header = self.get_header()
        file_header = self.get_file_header()
        if item in file_header:
            return header[file_header.index(item)]
        return None

    def check_header(self, header):
        """
        Function that verify if the header matches our expectations
        :param header: list
        :return: boolean
        """
        expected_header_fields = self.get_file_header()

        if len(expected_header_fields) != len(header):
            logger.error('Imported file header columns count %s does not match, expected %s columns.' %
                         (len(header), len(expected_header_fields)))
            return False

        for idx, header_field in enumerate(header):
            if header_field.lower() != expected_header_fields[idx].lower():
                logger.error('Imported header column "%s" does not match expected "%s".' %
                             (header_field.lower(), expected_header_fields[idx].lower()))
                return False

        logger.debug('File header meets our expectation. All expected columns were found, last column to be processed:'
                     ' %s.' % self.get_letter(len(header)))
        return True

    def process_row(self, vm, row, next_row):
        """
        Function that processes row, into server and html row.
        Server can contain multiple rows, before marked as completed.
        """
        disk = {}
        nic = {}
        html_row = {
            'errors': {},
            'info': {}
        }
        header = self.get_file_header()
        # header = get_file_header()

        for idx, field in enumerate(row):
            # skip everything that is outside header (we don't need +1 enumerate start from 0)
            if idx == len(header):
                break

            if field.value is not None:

                html_row[header[idx]] = field.value
                if header[idx] == 'vcpu':
                    vm[header[idx]] = int(field.value)
                elif header[idx] == 'ram':
                    vm[header[idx]] = int(1024 * float(field.value))
                elif header[idx] == 'network' or header[idx] == 'ip':
                    # Store rows that could be define multiple times
                    nic[header[idx]] = field.value
                elif header[idx] == 'image':
                    disk[header[idx]] = field.value
                elif header[idx] == 'hdd size':
                    disk[header[idx]] = int(1024 * float(field.value))
                else:
                    vm[header[idx]] = field.value
        if nic:
            vm['nic'].append(nic)
        if disk:
            vm['disk'].append(disk)
        vm['complete'] = False

        if next_row is False or not any([cell.value for cell in next_row[:len(header)]]) \
                or next_row[0].value is not None:
            vm['complete'] = True
            vm['json'] = json.dumps(vm)

        return vm, html_row

    def prepare_fields(self, vm, fields):
        bucket = {}

        for field in fields:
            if field in vm and vm[field] is not None:
                if field == 'os type':
                    for ostype in Vm.OSTYPE:
                        if vm['os type'] in ostype:
                            bucket[self.convert_file_header_to_header('os type')] = ostype[0]
                else:
                    bucket[self.convert_file_header_to_header(field)] = vm[field]

        return bucket

    def prepare_vm(self, vm):
        # Prepare vm
        vms = self.prepare_fields(vm, self.vm_fields)

        nics = []
        nic_fields = ('network', 'ip')
        for nic_details in vm['nic']:
            nic = self.prepare_fields(nic_details, nic_fields)
            nics.append(nic)

        disks = []
        disk_fields = ('storage', 'hdd size', 'image')  # , 'Backup')
        for disk_details in vm['disk']:
            disk = self.prepare_fields(disk_details, disk_fields)
            disks.append(disk)

        return vms, nics, disks

    @staticmethod
    def get_empty_vm():
        return {
            'hostname': None,  # **required** - Server hostname
            'alias': None,  # Short server name (default: hostname)
            'vcpu': None,  # **required** (if not specified in template) - Number of virtual CPUs inside VM (1-64)
            'ram': None,  # **required** (if not specified in template) - Size of RAM inside VM (32-524288 MB)
            'nic': [
                # {
                #     'network': None, # **required** - Name of VM Subnet
                #    'ip': None, # Virtual NIC IPv4 address.
                # }
            ],
            'disk': [
                # {
                #    'storage': None, # ???? Import as what ????? (zpool)
                #    'hdd size': None, # size: **required** (if not specified in image) - Disk size (10240-268435456 MB)
                #    'backup': None, # TOBE DONE in 2.1
                #    'image': None, # **required** (if size is not specified) - Disk image name
                # },
            ],
            'os type': None,  # **required** (if not specified in template) - Operating system type
                              # (1 - Linux VM, 2 - SunOS VM, 3 - BSD VM, 4 - Windows VM, 5 - SunOS Zone,
                              #  6 - Linux Zone)
            'tags': None,   # VM tags name (default: null)
            'node': None,   # Name of the host system
                            # (default: null => will be chosen automatically just before the VM is created)
        }
