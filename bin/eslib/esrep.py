import os
import time
import base64
import simplejson as json

try:
    # noinspection PyPep8Naming
    import cPickle as pickle
except ImportError:
    import pickle

from . import ERIGONES_HOME, ESLIB
from .cmd import CmdError, cmd_output, get_timestamp
from .zfs import ZFSCmd, get_snap_name, build_snapshot
from .smf import SMFCmd
from .tmpfile import TmpFile
from .filelock import filelock


class Replication(ZFSCmd, SMFCmd):
    """
    ZFS replication.
    """
    CMD = (os.path.join(ESLIB, 'esrep.sh'),)

    SERVICE_BASE_NAME = 'esrep-sync'
    SERVICE_NAME = 'application/' + SERVICE_BASE_NAME
    SERVICE_INSTANCE_NAME = 'slave-{slave_uuid}'
    SERVICE_INSTANCE_FMRI = 'svc:/%s:%s' % (SERVICE_NAME, SERVICE_INSTANCE_NAME)

    # Note: the esrep sync arguments order in start exec_method is important - see esrep-sync.sh script for details
    SERVICE_BUNDLE_MANIFEST = """<?xml version="1.0"?>
<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">
<service_bundle type='manifest' name='{base_name}'>
    <service name='{name}' type='service' version='0'>
        <dependency name='network' grouping='require_all' restart_on='none' type='service'>
            <service_fmri value='svc:/application/erigonesd:fast'/>
        </dependency>

        <method_context working_directory='{erigones_home}/var/run'>
            <method_credential user='root' group=':default' />
            <method_environment>
                <envvar name='ERIGONES_HOME' value='{erigones_home}' />
                <envvar name='PATH' value='{os_path}' />
                <envvar name='PYTHONPATH' value='{python_path}' />
                <envvar name='VIRTUAL_ENV' value='{erigones_home}/envs' />
            </method_environment>
        </method_context>

        <exec_method type='method' name='start' exec='{esrep_bin} sync -q -m %{{esrep/master}} -s %{{esrep/slave}} \
-H %{{esrep/master_host}} -i %{{esrep/id}} -t %{{esrep/sleep_time}} %{{esrep/opt_callback}} %{{esrep/opt_limit}}' \
timeout_seconds='60'>
        </exec_method>

        <exec_method type='method' name='stop' exec=':kill' timeout_seconds='300'>
        </exec_method>

        <property_group name='startd' type='framework'> <!-- esrep sync does not fork -->
             <propval name='duration' type='astring' value='child' />
        </property_group>

        <stability value='Evolving' />
    </service>
</service_bundle>
"""

    SERVICE_INSTANCE_MANIFEST = """<?xml version="1.0"?>
<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">
<service_bundle type='manifest' name='{base_name}'>
    <service name='{name}' type='service' version='0'>
        <instance name='{instance_name}' enabled='{enabled}'>
            <property_group name='esrep' type='application'>
                <propval name='master' type='astring' value='{master_uuid}' />
                <propval name='slave' type='astring' value='{slave_uuid}' />
                <propval name='master_host' type='astring' value='{master_host}' />
                <propval name='id' type='astring' value='{id}' />
                <propval name='sleep_time' type='astring' value='{sleep_time}' />
                <propval name='opt_callback' type='astring' value='{opt_callback}' />
                <propval name='opt_limit' type='astring' value='{opt_limit}' />
            </property_group>
        </instance>
    </service>
</service_bundle>
"""

    LOCK_DIR = os.path.abspath(os.path.join('/var', 'run'))
    DEST_VM_LOCK_FILE = lambda self, *args, **kwargs: os.path.join(self.LOCK_DIR, 'esrep-%s.lock' % self.dst_uuid)
    SRC_VM_LOCK_FILE = lambda self, *args, **kwargs: os.path.join(self.LOCK_DIR, 'esrep-%s.lock' % self.src_uuid)
    SERVICE_LOCK_FILE = os.path.join(LOCK_DIR, 'esrep.lock')

    ERR_VM_DISK_CHECK = 5
    ERR_VM_SNAP_CHECK = 6
    ERR_SVC_CHECK = 7

    json = None
    force = False
    quiet = False
    limit = None
    pickle = False
    sleep_time = None
    callback = None
    enabled = False
    id = 1

    _vm_sync = 0
    _vm_is_hvm = None
    _vm_cores_ds = None
    _vm_created = False
    _vm_disks = ()
    _vm_disks_snap = ()
    _vm_disks_synced = ()
    _snap_prefix_ = '@rs-%s-'
    _src_disk_property_ = 'esrep:dst:%s'
    _dst_disk_property_ = 'esrep:src:%s'
    _vm_disks_cleared = ()  # failover

    def __init__(self, src_uuid, dst_uuid, *args, **kwargs):
        self.src_uuid = src_uuid
        self.dst_uuid = dst_uuid
        self._vm_remote_json = {}
        self._vm_local_json = {}
        # kwargs will be saved by parent __init__() (including host and verbose)
        super(Replication, self).__init__(*args, **kwargs)

    @property
    def _esrep_bin(self):
        """esrep command run by the service"""
        # Conventional way:
        # return os.path.abspath(sys.argv[0])
        # Erigones wrapper:
        return os.path.join(ESLIB, 'esrep-sync.sh')

    @property
    def _snap_prefix(self):
        return self._snap_prefix_ % self.id

    @property
    def _src_disk_property(self):
        return self._src_disk_property_ % self.id

    @property
    def _dst_disk_property(self):
        return self._dst_disk_property_ % self.id

    def _is_bhyve(self):
        return self._vm_get_json(self.src_uuid, remote=True)['brand'] == 'bhyve'

    def _generate_snapshot_name(self):
        return self._snap_prefix + str(get_timestamp())

    def _list_dataset_snapshots(self, dataset, remote=False):
        snaps = self._run_cmd('_zfs_list_snapshots', dataset, remote=remote).split('\n')
        prefix = self._snap_prefix

        return (get_snap_name(snap.strip()) for snap in snaps if prefix in snap)  # Return flat generator

    def _destroy_snapshots(self, dataset, snapshots, remote=False):
        assert snapshots
        return self._destroy_dataset(build_snapshot(dataset, ','.join(snapshots)), remote=remote)

    def _is_dataset_property_empty(self, dataset, attr, remote=False):
        return self._get_dataset_property(dataset, attr, remote=remote) == '-'

    def _vm_check_disk_count(self, src_disks, dst_disks):
        if len(src_disks) != len(dst_disks):
            raise CmdError(self.ERR_VM_DISK_CHECK, 'Inconsistent disk configuration between master and slave VM')

    def _vm_create(self, vm_json, remote=False):
        return self._run_cmd('_vm_create', stdin=json.dumps(vm_json), remote=remote)

    def _vm_destroy(self, uuid, remote=False):
        try:
            self._run_cmd('_vm_remove_indestructible_property', uuid, remote=remote)
        except CmdError:
            pass

        return self._run_cmd('_vm_delete', uuid, remote=remote)

    def _vm_start(self, uuid, remote=False):
        return self._run_cmd('_vm_start', uuid, remote=remote)

    def _vm_stop(self, uuid, force=False, remote=False):
        if force:
            cmd = '_vm_stop_force'
        else:
            cmd = '_vm_stop'

        return self._run_cmd(cmd, uuid, remote=remote)

    def _vm_get_json(self, uuid, remote=False):
        def _get_json():
            return json.loads(self._run_cmd('_vm_json', uuid, remote=remote))

        # if value is cached, don't do query from host
        if remote:
            if self._vm_remote_json == {}:
                self._vm_remote_json = _get_json()
            return self._vm_remote_json
        else:
            if self._vm_local_json == {}:
                self._vm_local_json = _get_json()
            return self._vm_local_json

    def _vm_get_hostname(self, default=None, remote=False):
        if remote:
            vm_json = self._vm_remote_json
        else:
            vm_json = self._vm_local_json

        return vm_json.get('hostname', default)

    @property
    def src_hostname(self):
        return self._vm_get_hostname(remote=True)

    @property
    def dst_hostname(self):
        return self._vm_get_hostname()

    def _vm_get_disks(self, uuid, remote=False):
        cfg = self._vm_get_json(uuid, remote=remote)
        self._vm_is_hvm = (cfg['brand'] == 'kvm' or cfg['brand'] == 'bhyve')

        if self._vm_is_hvm:
            return [disk['zfs_filesystem'] for disk in cfg.get('disks', []) if disk.get('media', 'disk') == 'disk']
        else:
            return [cfg['zfs_filesystem']] + cfg.get('datasets', [])

    def _vm_get_disk_property(self, disk, full=False, remote=False, master=False):
        if master:
            vm_type = 'master'
            attr = self._src_disk_property
        else:
            vm_type = 'slave'
            attr = self._dst_disk_property

        try:
            hostname, disk = self._get_dataset_property(disk, attr, remote=remote).split('/', 1)

            if full:
                return hostname, disk
            else:
                return disk
        except (CmdError, IndexError, ValueError):
            raise CmdError(self.ERR_VM_DISK_CHECK, 'Could not read %s disk property on disk "%s"' % (vm_type, disk))

    def _send_recv(self, snapshot, dataset, incr_snapshot=None):
        cmd = ['zfs_send_recv', dataset, snapshot, self.host]

        if incr_snapshot:
            cmd.append(incr_snapshot)
        else:
            cmd.append('null')

        if self.limit:
            cmd.append(self.limit)

        return self._run_cmd(*cmd)

    def _sync_quota(self):
        src_json = self._vm_get_json(self.src_uuid, remote=True)
        dst_json = self._vm_get_json(self.dst_uuid, remote=False)
        src_vol = '%s/%s' % (src_json['zpool'], self.src_uuid)
        dst_vol = '%s/%s' % (dst_json['zpool'], self.dst_uuid)

        cmd = ['zfs_sync_quota', src_vol, dst_vol, self.host]
        return self._run_cmd(*cmd)

    def _prepare_dataset_destroy(self):
        """Umount core dataset when dealing with OS zone"""
        if not self._vm_is_hvm:
            cores_ds = '%s/cores/%s' % (self._vm_local_json['zpool'], self.dst_uuid)
            try:
                self._unmount_dataset(cores_ds)
            except CmdError as exc:
                if 'dataset does not exist' not in exc.msg:
                    raise exc
            else:
                self._vm_cores_ds = cores_ds

    def _finalize_initialized_vm(self):
        """Mount core dataset when dealing with OS zone"""
        if self._vm_cores_ds:
            self._mount_dataset(self._vm_cores_ds)

    def _create_new_snapshot(self, src_disk, dst_disk, snap_name, save_snap_info=True):
        """Create snapshot and save info about created snapshot for emergency cleanup"""
        snapshot = src_disk + snap_name
        self._create_snapshot(snapshot, remote=True)
        if save_snap_info:
            self._vm_disks_snap.append((src_disk, dst_disk, snap_name))

    def _should_be_synced(self, dataset):
        """Delegated dataset must not be synced"""
        return self._vm_is_hvm or dataset.count('/') < 2

    def _initial_sync(self, disks, src_host, dst_host, clear_src_disk_property=None, clear_dst_disk_property=None):
        """Initial sync used by init and reinit. This is the only place where esrep property values are constructed"""
        snap_name = self._generate_snapshot_name()
        self._vm_disks_snap = []
        self._vm_disks_synced = []

        # Create snapshots first
        for src_disk, dst_disk, incr_snapshot in disks:
            self._create_new_snapshot(src_disk, dst_disk, snap_name)  # Fill self._vm_disks_snap list

        # Sync
        for src, dst, incr_snapshot in disks:
            if self._should_be_synced(src):
                snapshot = src + snap_name
                self._send_recv(snapshot, dst, incr_snapshot=incr_snapshot)

            if clear_dst_disk_property:
                self._clear_dataset_property(dst, clear_dst_disk_property)

            self._set_dataset_properties(dst, {
                self._dst_disk_property: '%s/%s' % (src_host, src),
                'readonly': 'on'
            })

            if clear_src_disk_property:
                self._clear_dataset_property(src, clear_src_disk_property)

            self._set_dataset_properties(src, {
                self._src_disk_property: '%s/%s' % (dst_host, dst),
                'readonly': 'off'
            }, remote=True)

            self._vm_disks_synced.append((src, dst))  # Save info about synced disks for normal output

        return snap_name

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def init(self):
        """Initialize replication

        0. check disks;
        1. create slave VM;
        2. destroy target (local) VM disks;
        3. perform initial send/recv.

        Run on destination host (host of slave VM); so "src" is remote (master) and "dst" is local (slave)
        """
        src_uuid, dst_uuid, dst_json = self.src_uuid, self.dst_uuid, self.json
        assert dst_uuid == dst_json['uuid']

        dst_host_name = self._get_hostname()
        src_host_name = self._check_host(hostname=True)  # This is the remote host
        self._vm_create(dst_json)
        self._vm_created = dst_uuid
        dst_disks = self._vm_get_disks(dst_uuid)
        src_disks = self._vm_get_disks(src_uuid, remote=True)

        self._vm_check_disk_count(src_disks, dst_disks)
        self._prepare_dataset_destroy()

        for disk in reversed(dst_disks):  # First destroy the delegated dataset in case of a zone
            self._destroy_dataset(disk)

        if dst_json['brand'] == 'bhyve':
            self._sync_quota()

        # Initial sync will create destination datasets and set metadata on both
        vm_disks = zip(src_disks, dst_disks, [None] * len(src_disks))
        last_snap = self._initial_sync(vm_disks, src_host_name, dst_host_name)
        self._finalize_initialized_vm()
        slave_json = self._vm_get_json(dst_uuid)

        if self.pickle:
            slave_json = base64.encodestring(pickle.dumps(slave_json))

        return {
            'master': src_uuid,
            'master_hostname': self.src_hostname,
            'master_host': src_host_name,
            'master_disks': src_disks,
            'slave': dst_uuid,
            'slave_hostname': self.dst_hostname,
            'slave_host': dst_host_name,
            'slave_disks': dst_disks,
            'synced_disks': self._vm_disks_synced,
            'snapshot_name': last_snap,
            'timestamp': int(last_snap.split('-')[-1]),
            'slave_json': slave_json,
        }

    # noinspection PyUnusedLocal
    def init_cleanup(self, response):
        """Initialization failed - destroy slave VM (vmadm will delete all datasets) and
        created replication snapshots on master and replication metadata on master"""
        for src, dst in self._vm_disks_synced:
            self._clear_dataset_property(src, self._src_disk_property, remote=True)

        if self._vm_created:
            # Destroy slave VM
            self._vm_destroy(self._vm_created)

            for src, dst, snap in self._vm_disks_snap:
                try:
                    self._destroy_dataset(src + snap, remote=True)
                except CmdError:
                    pass

    def _vm_get_host_and_disks(self, uuid, remote=False, force=False):
        """Get src/dst hostname and disks; apply force if requested"""
        hostname = None
        disks = ()

        try:
            if remote:
                hostname = self._check_host(hostname=True)
            else:
                hostname = self._get_hostname()
        except CmdError:
            if not force:
                raise
        else:
            try:
                disks = self._vm_get_disks(uuid, remote=remote)
            except CmdError:
                if not force:
                    raise

        return hostname, disks

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def destroy(self):
        """Disable replication

        0. check disks;
        1. destroy slave VM (including disks);
        2. remove replication snapshots and metadata from master disks
           (skipped if force=True and master is unreachable).

        Run on destination host (host of slave VM)
        """
        check_master = not self.force
        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True, force=self.force)

        if check_master:
            self._vm_check_disk_count(src_disks, dst_disks)

        for i, dst_disk in enumerate(dst_disks):
            # Let's make sure that the local disk is a slave disk
            dst_disk_property = self._vm_get_disk_property(dst_disk)

            if check_master:
                if dst_disk_property != src_disks[i]:
                    raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave disk "%s" is not synced with master disk "%s"' %
                                   (dst_disk, src_disks[i]))
            elif self.src_uuid not in dst_disk_property:  # Simple check
                raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave disk "%s" is not synced with master disk' % dst_disk)

        # SMF manifest check - it should not exist at this point
        if self._service_instance_exists(self._svc_instance_fmri):
            raise CmdError(self.ERR_SVC_CHECK, 'Replication service must be removed before destroy')

        # Destroy slave VM
        self._vm_destroy(self.dst_uuid)
        # From now on everything we do must _not_ raise an exception
        cleaned_src_disks = []

        for i, src_disk in enumerate(src_disks):  # src_disks will be empty if VM/host is not available
            # Remove replication snapshots and clear master disk properties in any case, but fail silently
            try:
                esrep_snapshots = list(self._list_dataset_snapshots(src_disk, remote=True))

                if esrep_snapshots:
                    self._destroy_snapshots(src_disk, esrep_snapshots, remote=True)

                src_disk_property = self._vm_get_disk_property(src_disk, master=True, remote=True)

                if src_disk_property == dst_disks[i]:
                    self._clear_dataset_property(src_disk, self._src_disk_property, remote=True)
                    cleaned_src_disks.append(src_disk)
            except (CmdError, IndexError):
                continue

        return {
            'slave': self.dst_uuid,
            'slave_hostname': self.dst_hostname,
            'slave_disks': dst_disks,
            'slave_host': dst_host_name,
            'master': self.src_uuid,
            'master_hostname': self.src_hostname,
            'master_disks': src_disks,
            'master_host': src_host_name,
            'master_cleaned_disks': cleaned_src_disks,
        }

    def _clear(self, src_disks, remote=False):
        """Clear replication stuff from master VM"""
        cleaned_src_disks = []

        for src_disk in src_disks:
            # Make sure that this is not a slave
            if not self._is_dataset_property_empty(src_disk, self._dst_disk_property, remote=remote):
                raise CmdError(self.ERR_VM_DISK_CHECK, 'Master disk "%s" does look like a slave disk!')

            # The master VM disk property may be cleared after failover
            src_disk_property = not self._is_dataset_property_empty(src_disk, self._src_disk_property, remote=remote)

            if src_disk_property:
                self._clear_dataset_property(src_disk, self._src_disk_property, remote=remote)

            esrep_snapshots = list(self._list_dataset_snapshots(src_disk, remote=remote))

            if esrep_snapshots:
                self._destroy_snapshots(src_disk, esrep_snapshots, remote=remote)

            if src_disk_property or esrep_snapshots:
                cleaned_src_disks.append(src_disk)

        return cleaned_src_disks

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def destroy_clear(self):
        """Destroy slave VM and cleanup replication stuff from master VM

        0. check disks;
        1. destroy slave VM (including disks);
        2. remove replication snapshots and metadata from master disks.

        Run on destination host (host of slave - old master VM)
        """
        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True)

        # SMF manifest check - it should not exist at this point
        if self._service_instance_exists(self._svc_instance_fmri):
            raise CmdError(self.ERR_SVC_CHECK, 'Replication service must be removed before destroy')

        # Destroy slave VM
        self._vm_destroy(self.dst_uuid)
        # Cleanup master VM
        cleaned_src_disks = self._clear(src_disks, remote=True)

        return {
            'slave': self.dst_uuid,
            'slave_hostname': self.dst_hostname,
            'slave_disks': dst_disks,
            'slave_host': dst_host_name,
            'master': self.src_uuid,
            'master_hostname': self.src_hostname,
            'master_disks': src_disks,
            'master_host': src_host_name,
            'master_cleaned_disks': cleaned_src_disks,
        }

    @cmd_output
    @filelock(SRC_VM_LOCK_FILE)
    def clear(self):
        """Cleanup replication stuff from master VM

        0. check disks;
        1. remove replication snapshots and metadata from master disks.

        Run on source host (host of master VM)!
        """
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid)
        # Cleanup master VM
        cleaned_src_disks = self._clear(src_disks)

        return {
            'master': self.src_uuid,
            'master_hostname': self._vm_get_hostname(),
            'master_disks': src_disks,
            'master_host': src_host_name,
            'master_cleaned_disks': cleaned_src_disks,
        }

    def _vm_check_disk_sync(self, src_disk, dst_disk):
        """Validate disk synchronization by checking disk metadata"""
        if self._vm_get_disk_property(dst_disk) != src_disk:
            raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave VM disk "%s" is not initialized with master VM disk "%s"'
                           % (dst_disk, src_disk))

        if self._vm_get_disk_property(src_disk, master=True, remote=True) != dst_disk:
            raise CmdError(self.ERR_VM_DISK_CHECK, 'Master VM disk "%s" is not initialized with slave VM disk "%s"'
                           % (src_disk, dst_disk))

    def _get_common_snapshot(self, src_disk, dst_disk):
        """List snapshots for both disks and find a common snapshot"""
        dst_snapshots = list(self._list_dataset_snapshots(dst_disk))
        src_snapshots = list(self._list_dataset_snapshots(src_disk, remote=True))

        for snap in reversed(src_snapshots):  # The snapshots are originally ordered from oldest to newest
            if snap in dst_snapshots:
                last_snap_name = '@' + snap
                break
        else:
            raise CmdError(self.ERR_VM_SNAP_CHECK, 'Master VM disk "%s" and slave VM disk "%s" do not have '
                                                   'a common snapshot' % (src_disk, dst_disk))

        return last_snap_name, src_snapshots, dst_snapshots

    def _sync_disk(self, src_disk, dst_disk, incr_snap_name, snap_name, destroy_incr_snapshot=True):
        """VM sync: perform sync (send/recv) of one disk"""
        new_src_snapshot = src_disk + snap_name
        incr_src_snapshot = src_disk + incr_snap_name
        incr_dst_snapshot = dst_disk + incr_snap_name

        if self._should_be_synced(src_disk):
            self._send_recv(new_src_snapshot, dst_disk, incr_snapshot=incr_src_snapshot)

        if destroy_incr_snapshot:
            self._destroy_dataset(incr_src_snapshot, remote=True)
            self._destroy_dataset(incr_dst_snapshot)
        else:
            # Emergency snapshot cleanup is required only for the first/cold sync
            del self._vm_disks_snap[0]  # Disk synced - remove info for emergency cleanup

    def _cold_sync(self, vm_disks):
        """VM sync: perform sync (send/recv) of all disks and remove old snapshots"""
        new_snap = self._generate_snapshot_name()
        self._vm_disks_snap = []
        self._vm_disks_synced = []

        for i in vm_disks:
            self._create_new_snapshot(i[0], i[1], new_snap)  # Fill self._vm_disks_snap list

        for src_disk, dst_disk, incr_snap, src_snaps, dst_snaps in vm_disks:
            self._sync_disk(src_disk, dst_disk, incr_snap, new_snap, destroy_incr_snapshot=False)
            self._destroy_snapshots(src_disk, src_snaps, remote=True)
            self._destroy_snapshots(dst_disk, dst_snaps)
            self._vm_disks_synced.append((src_disk, dst_disk))  # Save info about synced disks for normal output

        return new_snap

    def _hot_sync(self, incr_snap):
        """VM sync: perform sync (send/recv) of all disks and remove incremental snapshot"""
        new_snap = self._generate_snapshot_name()
        del self._vm_disks_synced[:]

        for src_disk, dst_disk in self._vm_disks:
            self._create_new_snapshot(src_disk, dst_disk, new_snap, save_snap_info=False)

        for src_disk, dst_disk in self._vm_disks:
            self._sync_disk(src_disk, dst_disk, incr_snap, new_snap)
            self._vm_disks_synced.append((src_disk, dst_disk))

        return new_snap

    def _run_callback(self, response):
        """Run user defined callback after successful sync with response as argument"""
        if self.callback:
            try:
                response.pop('callback_error', None)
                # noinspection PyCallingNonCallable
                self.callback(response, *self.callback.args)
            except Exception as exc:
                response['callback_error'] = '%s: %s' % (exc.__class__.__name__, exc)

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def sync(self):
        """VM sync

        0. check disks;
        1. fetch master and slave disk pairs;
        2. perform sync (send/recv).

        Run on destination host (host of slave VM)"""
        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True)
        self._vm_check_disk_count(src_disks, dst_disks)
        vm_disks = []

        # sync quota before syncing disks (quota might have been increased since last sync)
        if self._is_bhyve():
            self._sync_quota()

        # Check replication metadata and fetch common snapshot
        for src_disk, dst_disk in zip(src_disks, dst_disks):
            self._vm_check_disk_sync(src_disk, dst_disk)
            last_snap_name, src_snapshots, dst_snapshots = self._get_common_snapshot(src_disk, dst_disk)
            vm_disks.append((src_disk, dst_disk, last_snap_name, src_snapshots, dst_snapshots))

        # Perform first incremental sync (send/recv)
        last_snap = self._cold_sync(vm_disks)
        self._vm_sync = 1
        res = {
            'master': self.src_uuid,
            'master_hostname': self.src_hostname,
            'master_host': src_host_name,
            'master_disks': [i[0] for i in vm_disks],
            'slave': self.dst_uuid,
            'slave_hostname': self.dst_hostname,
            'slave_host': dst_host_name,
            'slave_disks': [i[1] for i in vm_disks],
            'synced_disks': self._vm_disks_synced,
            'snapshot_name': last_snap,
            'timestamp': int(last_snap.split('-')[-1]),
            'sync': self._vm_sync,
        }

        if self.sleep_time is not None:
            self._vm_disks = tuple(self._vm_disks_synced)
            sleep_time = float(self.sleep_time)
            verbose = not self.quiet

            while True:
                try:
                    self._run_callback(res)
                    if verbose:
                        self.print_output(res)
                    time.sleep(sleep_time)
                except KeyboardInterrupt:
                    return res

                last_snap = self._hot_sync(last_snap)
                self._vm_sync += 1
                res['sync'] = self._vm_sync
                res['snapshot_name'] = last_snap
                res['timestamp'] = int(last_snap.split('-')[-1])
        else:
            self._run_callback(res)

            return res

    # noinspection PyUnusedLocal
    def sync_cleanup(self, response):
        """Remove created snapshots for failed cold sync (send/recv)"""
        response['sync'] = self._vm_sync  # Successful sync counter

        for src_disk, dst_disk, snap in self._vm_disks_snap:
            try:
                self._destroy_dataset(src_disk + snap, remote=True)
            except CmdError:
                pass

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def failover(self):
        """Promote slave to master (keep original master untouched)

        Run on destination host (host of slave VM)"""
        check_master = not self.force
        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True, force=self.force)
        dst_disk_properties = []

        if check_master:
            self._vm_check_disk_count(src_disks, dst_disks)

        # 0. Check original slave's disks
        for i, dst_disk in enumerate(dst_disks):
            # Let's make sure that the local disk is a slave disk
            dst_disk_property = self._vm_get_disk_property(dst_disk, full=True)
            dst_disk_properties.append((dst_disk, '/'.join(dst_disk_property)))

            if check_master:
                if dst_disk_property[1] != src_disks[i]:
                    raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave disk "%s" is not synced with master disk "%s"' %
                                   (dst_disk, src_disks[i]))
            elif self.src_uuid not in dst_disk_property[1]:  # Simple check
                raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave disk "%s" is not synced with master disk' % dst_disk)

        # 1. Check replication metadata on original master's disks
        #    (skip this step if force=True)
        if check_master:
            for i, src_disk in enumerate(src_disks):  # src_disks will be empty if VM/host is not available
                src_disk_property = self._vm_get_disk_property(src_disk, master=True, remote=True)

                if src_disk_property != dst_disks[i]:
                    raise CmdError(self.ERR_VM_DISK_CHECK, 'Master disk "%s" is not synced with slave disk "%s"' %
                                   (src_disk, dst_disks[i]))

        # 2. SMF manifest check - it should not exist at this point
        if self._service_instance_exists(self._svc_instance_fmri):
            raise CmdError(self.ERR_SVC_CHECK, 'Replication service must be removed before failover')

        # 3. Promote original slave to master
        #    a) try to stop original master
        #    b) clear replication metadata on original slave's disks
        #    c) start new master (original slave)
        old_master_stopped = False

        try:
            self._vm_stop(self.src_uuid, force=True, remote=True)
        except CmdError:
            if check_master:
                raise
        else:
            old_master_stopped = True

        self._vm_disks_cleared = []
        for dst_disk, dst_disk_property in dst_disk_properties:
            self._clear_dataset_property(dst_disk, self._src_disk_property)  # Remove both properties, because the
            self._clear_dataset_property(dst_disk, self._dst_disk_property)  # esrep:dst is received by slave via sync
            self._vm_disks_cleared.append((dst_disk, dst_disk_property))
            self._clear_dataset_property(dst_disk, 'readonly')

        self._vm_start(self.dst_uuid)
        self._vm_disks_cleared = []  # Start was successful

        return {
            'new_master': self.dst_uuid,
            'new_master_disks': dst_disks,
            'new_master_host': dst_host_name,
            'new_master_hostname': self.dst_hostname,
            'old_master': self.src_uuid,
            'old_master_hostname': self.src_hostname,
            'old_master_disks': src_disks,
            'old_master_host': src_host_name,
            'old_master_stopped': old_master_stopped,
        }

    # noinspection PyUnusedLocal
    def failover_cleanup(self, response):
        """The failover procedure may fail and leave the original slave with missing disk properties"""
        if self._vm_disks_cleared:
            try:
                self._vm_stop(self.dst_uuid, force=True)  # just in case
            except CmdError:
                pass

            # Restore original slave disk properties
            for dst_disk, dst_disk_property in self._vm_disks_cleared:
                self._set_dataset_properties(dst_disk, {
                    self._dst_disk_property: dst_disk_property,
                    'readonly': 'on'
                })

    @cmd_output
    @filelock(DEST_VM_LOCK_FILE)
    def reinit(self):
        """Degrade old master to slave and re-initialize replication

        You should run the sync sub-command after successful reinit.
        Run on new destination host (host of old master VM) so "src" is remote (new master) and
                                                               "dst" is local (old master - new slave)"""
        # After a successful failover the old master is left untouched and should be degraded or destroyed
        # But first stop it no mather what
        self._vm_stop(self.dst_uuid, force=True)

        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True)
        vm_disks = []

        # 0. Perform disk checks and find a common snapshot
        #    a) check if slave's disks are configured as old master's disks
        #    b) check if new master's disks have no slave metadata (cleared by successful failover)
        #    c) fetch snapshots and find latest common snapshot
        for src_disk, dst_disk in zip(src_disks, dst_disks):
            if not (self._vm_get_disk_property(dst_disk, master=True) == src_disk and
                    self._get_dataset_property(dst_disk, 'readonly') == 'off'):
                raise CmdError(self.ERR_VM_DISK_CHECK, 'Slave (old master) VM disk "%s" was not initialized'
                                                       'with new master VM disk "%s"' % (dst_disk, src_disk))

            if not (self._is_dataset_property_empty(src_disk, self._src_disk_property, remote=True) and
                    self._is_dataset_property_empty(src_disk, self._dst_disk_property, remote=True) and
                    self._get_dataset_property(src_disk, 'readonly', remote=True) == 'off'):
                raise CmdError(self.ERR_VM_DISK_CHECK, 'Master disk "%s" has replication metadata set' % src_disk)

            last_snap_name, src_snapshots, dst_snapshots = self._get_common_snapshot(src_disk, dst_disk)
            vm_disks.append((src_disk, dst_disk, last_snap_name))

        # Perform sync (send/recv) of all disks and set metadata on both disks
        last_snap = self._initial_sync(vm_disks, src_host_name, dst_host_name,
                                       clear_dst_disk_property=self._src_disk_property)

        return {
            'master': self.src_uuid,
            'master_hostname': self.src_hostname,
            'master_host': src_host_name,
            'master_disks': src_disks,
            'slave': self.dst_uuid,
            'slave_hostname': self.dst_hostname,
            'slave_host': dst_host_name,
            'slave_disks': dst_disks,
            'synced_disks': self._vm_disks_synced,
            'snapshot_name': last_snap,
            'timestamp': int(last_snap.split('-')[-1]),
        }

    def reinit_cleanup(self, response):
        """Re-initialization failed - remove created snapshots for failed syncs (send/recv), but
        KEEP synced datasets untouched  - this is the only situation where previous state is not restored!"""
        response['synced_disks'] = self._vm_disks_synced

        if self._vm_disks_snap:
            synced_disks = dict(self._vm_disks_synced)  # {src: dst}

            for src_disk, dst_disk, snap in self._vm_disks_snap:
                if src_disk not in synced_disks:
                    try:
                        self._destroy_dataset(src_disk + snap, remote=True)
                    except CmdError:
                        pass

    @property
    def _svc_instance_name(self):
        """Return replication service instance name created from master and slave VM's uuids"""
        return self.SERVICE_INSTANCE_NAME.format(master_uuid=self.src_uuid, slave_uuid=self.dst_uuid, id=self.id)

    @property
    def _svc_instance_fmri(self):
        """Replication service instance is always named after master and slave VM's uuids"""
        return self.SERVICE_INSTANCE_FMRI.format(master_uuid=self.src_uuid, slave_uuid=self.dst_uuid, id=self.id)

    @property
    def _svc_bundle_manifest(self):
        """Return SMF bundle manifest"""
        return self.SERVICE_BUNDLE_MANIFEST.format(name=self.SERVICE_NAME,
                                                   base_name=self.SERVICE_BASE_NAME,
                                                   erigones_home=ERIGONES_HOME,
                                                   os_path=os.environ.get('PATH', ''),
                                                   python_path=os.environ.get('PYTHONPATH', ''),
                                                   esrep_bin=self._esrep_bin)

    @property
    def _svc_instance_manifest(self):
        """Return SMF instance manifest named after master and slave VM's uuids"""
        if self.callback:
            opt_callback = '-c%s' % self.callback.orig_name
        else:
            opt_callback = ''

        if self.limit:
            opt_limit = '-l%s' % self.limit
        else:
            opt_limit = ''

        return self.SERVICE_INSTANCE_MANIFEST.format(name=self.SERVICE_NAME,
                                                     base_name=self.SERVICE_BASE_NAME,
                                                     instance_name=self._svc_instance_name,
                                                     enabled=str(bool(self.enabled)).lower(),
                                                     master_uuid=self.src_uuid,
                                                     slave_uuid=self.dst_uuid,
                                                     master_host=self.host,
                                                     id=self.id,
                                                     sleep_time=self.sleep_time,
                                                     opt_callback=opt_callback,
                                                     opt_limit=opt_limit)

    def _svc_status(self):
        """Return service status"""
        fmri = self._svc_instance_fmri

        return {
            'master': self.src_uuid,
            'slave': self.dst_uuid,
            'service_name': fmri,
            'service_state': self._service_status(fmri),
        }

    @cmd_output
    def svc_status(self):
        """
        Return sync service status identified by master/slave VM uuids. Run on destination host (host of slave VM).
        """
        return self._svc_status()

    @cmd_output
    def svc_enable(self):
        """
        Stop sync service identified by master/slave VM uuids. Run on destination host (host of slave VM).
        """
        self._service_enable(self._svc_instance_fmri)

        return self._svc_status()

    @cmd_output
    def svc_disable(self):
        """
        Start sync service identified by master/slave VM uuids. Run on destination host (host of slave VM).
        """
        self._service_disable(self._svc_instance_fmri)

        return self._svc_status()

    @cmd_output
    @filelock(SERVICE_LOCK_FILE)
    def svc_create(self):
        """
        Add sync service instance identified by master/slave VM uuids. Run on destination host (host of slave VM).
        """
        # Validate master and slave VM uuids and disks
        dst_host_name, dst_disks = self._vm_get_host_and_disks(self.dst_uuid)
        src_host_name, src_disks = self._vm_get_host_and_disks(self.src_uuid, remote=True)
        self._vm_check_disk_count(src_disks, dst_disks)

        # Check replication metadata
        for src_disk, dst_disk in zip(src_disks, dst_disks):
            self._vm_check_disk_sync(src_disk, dst_disk)

        # Check if service bundle exists
        if not self._service_exists(self.SERVICE_NAME):
            # Define service bundle without any instance
            with TmpFile(self._svc_bundle_manifest, text=True) as f:
                self._service_import(self.SERVICE_NAME, f.name)

        # Import service instance
        with TmpFile(self._svc_instance_manifest, text=True) as f:
            self._service_instance_import(self.SERVICE_NAME, f.name)

        res = self._svc_status()
        res.update({
            'sleep_time': self.sleep_time,
            'enabled': self.enabled,
            'bwlimit': self.limit,
            'callback': self.callback.orig_name if self.callback else None,
        })

        return res

    @cmd_output
    @filelock(SERVICE_LOCK_FILE)
    def svc_remove(self):
        """
        Delete sync service instance identified by master/slave VM uuids. Run on destination host (host of slave VM).
        """
        self._service_disable(self._svc_instance_fmri)
        self._service_instance_delete(self.SERVICE_NAME, self._svc_instance_name)

        return {
            'master': self.src_uuid,
            'slave': self.dst_uuid,
            'service_name': self._svc_instance_fmri,
            'service_state': 'absent',
        }
