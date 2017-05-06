from hashlib import sha1
from collections import defaultdict, namedtuple
import os
import json

from . import ESLIB
from .cmd import CmdError, cmd_output, get_timestamp
from .zfs import ZFSCmd, get_snap_name, get_snap_dataset, build_snapshot, switch_snap_dataset
from .cmd_args import long_int


class Backup(ZFSCmd):
    """
    ZFS Backup.
    """
    CMD = (os.path.join(ESLIB, 'esbackup.sh'),)

    BKPDIR_MODE = 0o750
    SNAP_PREFIX = '@is-'
    ARCHIVE_FLAG = 'arch'
    NAME_PROPERTY = 'es:bkpname'
    KEEP_PROPERTIES = ('type', 'volsize', 'volblocksize', 'compression', 'refreservation', 'reservation', 'quota',
                       'recordsize', 'zoned')

    ERR_DATASET_CHECK = 4
    ERR_FILE_CHECK = 5

    # create cleanup attributes
    update_snapshots = ()  # List of dicts with name and new_name attributes, which were renamed during archivation
    last_snapshot = None  # Last snapshot created on original dataset
    deleted_last_snapshot_names = ()  # List of snapshots on original dataset, which were deleted by the backup process
    metadata_file = None  # Metadata file created for last backup (used in both dataset and file)

    # delete cleanup attributes
    affected_datasets = ()
    deleted_snapshots = ()

    # restore helper attribute
    filesystem = False
    zoned = False

    # file_delete cleanup attributes
    deleted_files = ()

    # Init flags
    compression = None
    limit = None

    @classmethod
    def _new_dataset_archive(cls, dataset):
        return '%s-%s-%s' % (dataset, cls.ARCHIVE_FLAG, get_timestamp())

    @classmethod
    def _rename_snapshots(cls, snapshots, new_dataset):
        snap_update = namedtuple('Snapshot', ('name', 'new_name'))

        return [snap_update(snap, switch_snap_dataset(snap, new_dataset)) for snap in snapshots]

    #
    # File backup methods
    #

    @staticmethod
    def _get_file_checksum(filename, blocksize=65536):
        with open(filename, 'rb') as f:
            hasher = sha1()
            buf = f.read(blocksize)

            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(blocksize)

        return hasher.hexdigest()

    @staticmethod
    def _get_file_size(filename):
        return os.path.getsize(filename)

    @staticmethod
    def _delete_file(filename):
        return os.remove(filename)

    @classmethod
    def _delete_file_silent(cls, filename):
        try:  # Cleanup
            return cls._delete_file(filename)
        except OSError:
            pass

    @classmethod
    def _create_backup_dir(cls, directory):
        if not os.path.exists(directory):
            return os.makedirs(directory, cls.BKPDIR_MODE)

    @classmethod
    def _check_file(cls, filename):
        if not os.path.isfile(filename):
            raise CmdError(cls.ERR_FILE_CHECK, 'File "%s" is not available' % filename)

    @classmethod
    def _check_dir(cls, directory):
        if not os.path.isdir(directory):
            raise CmdError(cls.ERR_FILE_CHECK, 'Backup directory is not available')

    def _backup_to_file(self, dataset, filename, fsfreeze=None):
        compression = self.compression or 'null'
        limit = self.limit or 'null'

        if self.host:
            cmd = ['zfs_file_backup_remote', dataset, filename, self.host, compression, limit]
        else:
            cmd = ['zfs_file_backup_local', dataset, filename, compression, limit]

        if fsfreeze:
            cmd.append(fsfreeze)

        return self._run_cmd(*cmd)

    def _restore_file(self, filename, dataset):
        if self.host:
            cmd = ['zfs_file_restore_remote', filename, dataset, self.host]
        else:
            cmd = ['zfs_file_restore_local', filename, dataset]

        return self._run_cmd(*cmd, remote=False)

    #
    # Dataset backup methods
    #

    def _check_dataset(self, dataset, remote=False):
        try:
            return self._run_cmd('_zfs_dataset_exists', dataset, remote=remote)
        except CmdError as e:
            raise CmdError(self.ERR_DATASET_CHECK, 'Invalid dataset (%s)' % e.msg)

    def _destroy_all_snapshots(self, dataset, remote=False):
        return self._run_cmd('_zfs_destroy_snapshots', dataset, remote=remote)

    def _create_dataset(self, dataset, ds_type, properties, remote=False):
        props = ['%s=%s' % kv for kv in properties.items()]

        return self._run_cmd('_zfs_dataset_create', dataset, ds_type, *props, remote=remote)

    def _list_dataset_snapshots(self, dataset, properties=('name',), remote=False):
        snaps = self._run_cmd('_zfs_list_snapshots', dataset, ','.join(properties), remote=remote).split('\n')
        prefix = self.SNAP_PREFIX

        if len(properties) > 1:
            snapshot = namedtuple('Snapshot', properties)
            return (snapshot(*snap.split()) for snap in snaps if prefix in snap)  # Return list of named tuples
        else:
            return (snap for snap in snaps if prefix in snap)  # Return flat list

    def _rename_dataset(self, cur_dataset, new_dataset, set_zoned=False, remote=False):
        cmd = ['_zfs_dataset_rename', cur_dataset, new_dataset]

        if set_zoned:
            cmd.append('true')

        return self._run_cmd(*cmd, remote=remote)

    def _rename_dataset_children(self, cur_dataset, new_dataset, set_zoned=False, remote=False):
        cmd = ['_zfs_rename_children', cur_dataset, new_dataset]

        if set_zoned:
            cmd.append('true')

        return self._run_cmd(*cmd, remote=remote)

    def _backup_dataset(self, snapshot, dataset, incr_snapshot=None):
        if self.host:
            cmd = ['zfs_dataset_backup_remote', dataset, snapshot, self.host]
        else:
            cmd = ['zfs_dataset_backup_local', dataset, snapshot]

        if incr_snapshot:
            cmd.append(incr_snapshot)
        else:
            cmd.append('null')

        if self.limit:
            cmd.append(self.limit)

        return self._run_cmd(*cmd)

    def _backup_and_create_empty_dataset(self, dataset, remote=False):
        # Check dataset existence and get important properties
        props = self._get_dataset_properties(dataset, self.KEEP_PROPERTIES, remote=remote)
        ds_type = props.pop('type')
        ds_zoned = props.pop('zoned', None)

        if ds_type == 'volume':
            ds_type = props.pop('volsize')
        else:
            self.zoned = ds_zoned == 'on'
            self.filesystem = True
            # Remove zoned attribute from children datasets (will skip the parent dataset)
            self._set_dataset_property(dataset, 'zoned', 'off', children=True, remote=remote)

        if self.zoned:  # Remove zoned attribute before rename
            self._set_dataset_property(dataset, 'zoned', 'off', remote=remote)
            props['zoned'] = 'on'  # Create new dataset with zoned=on

        ds_backup = '%s-esbackup-%s' % (dataset, get_timestamp())
        self._rename_dataset(dataset, ds_backup, remote=remote)  # Move current dataset

        try:
            self._create_dataset(dataset, ds_type, props, remote=remote)  # Create empty dataset
        except CmdError:
            self._rename_dataset(ds_backup, dataset, set_zoned=self.zoned, remote=remote)  # Rollback

            if self.filesystem:  # Return zoned attribute to child datasets
                self._set_dataset_property(dataset, 'zoned', 'on', children=True, remote=remote)

            raise  # Re-raise

        return ds_backup

    def _restore_dataset(self, snapshot, dataset):
        if self.host:
            cmd = ['zfs_dataset_restore_remote', snapshot, dataset, self.host]
        else:
            cmd = ['zfs_dataset_restore_local', snapshot, dataset]

        return self._run_cmd(*cmd, remote=False)

    def _list_dataset_snapshot_size(self):
        """Used by ds_delete and ds_delete_cleanup"""
        res = []

        if not self.deleted_snapshots or not self.affected_datasets:
            return res

        for dataset in self.affected_datasets:
            try:
                res.extend(list(self._list_dataset_snapshots(dataset, properties=('name', 'written'))))
            except CmdError:
                continue  # Ignore errors here, because this should not affect the success or failure output

        return res

    def _remove_json_metadata_file(self, jsonfile):
        """Delete JSON file with metadata silently: if this fails backup is removed anyway."""
        self._delete_file_silent(jsonfile)
        self.metadata_file = None

    def _store_json_metadata_to_file(self, jsonfile, data):
        """Store JSON into file and create directories if they do not exists"""
        self._create_backup_dir(os.path.dirname(jsonfile))

        with open(jsonfile, 'w+') as outfile:
            json.dump(data, outfile)

        self.metadata_file = jsonfile

    def cleanup(self, action, response):
        """Emergency rollback - run action_cleanup() method"""
        fun = getattr(self, '%s_cleanup' % action, None)

        if fun:
            self.log('Running cleanup for "%s" action' % action)
            fun(response)

    #
    # Public methods - actions
    #

    def ds_create_cleanup(self, response):
        response['update_snapshots'] = self.update_snapshots
        response['deleted_last_snapshot_names'] = self.deleted_last_snapshot_names

        if self.metadata_file:
            self._remove_json_metadata_file(self.metadata_file)  # Silent operation

        response['metadata_file'] = self.metadata_file

        if self.last_snapshot:
            try:
                self._destroy_dataset(self.last_snapshot, remote=True)
            except CmdError:
                response['last_snapshot_name'] = get_snap_name(self.last_snapshot)

    @cmd_output
    def ds_create(self, snapshot, destination, name, metadata=None, json=None, fsfreeze=None):
        """Create snapshot on remote host and send it here"""
        ds = destination.split('/')

        if len(ds) < 3:
            raise CmdError(self.ERR_DATASET_CHECK, 'Invalid destination dataset')

        remote_ds, snap_name = snapshot.split('@')
        incr_snap = None
        self._check_dataset('/'.join(ds[:-1]))  # Check parent dataset (zones/backups/ds)
        self._check_host()  # Check SSH if needed
        self.deleted_last_snapshot_names = []
        remote_snapshots = [get_snap_name(s) for s in self._list_dataset_snapshots(remote_ds, remote=True)]

        if metadata and json:
            # Create metadata file first, if it fails we dont need to create backup, clean up would remove it anyways.
            self._store_json_metadata_to_file(metadata, json)

        if self._dataset_exists(destination):
            local_snapshots = list(self._list_dataset_snapshots(destination))

            try:
                most_recent_snapshot = get_snap_name(local_snapshots[-1])
            except IndexError:  # This should never happen
                raise CmdError(self.ERR_UNKNOWN, 'Backup destination exists, but has no snapshots')

            if most_recent_snapshot in remote_snapshots:
                incr_snap = build_snapshot(remote_ds, most_recent_snapshot)
                remote_snapshots.remove(most_recent_snapshot)
            else:
                # Archive backup dataset
                archive_ds = self._new_dataset_archive(destination)
                self._rename_dataset(destination, archive_ds)
                self.update_snapshots = self._rename_snapshots(local_snapshots, archive_ds)

        if remote_snapshots:  # Remaining incremental snapshots on original dataset are useless now
            self._destroy_dataset(build_snapshot(remote_ds, ','.join(remote_snapshots)), remote=True)
            self.deleted_last_snapshot_names = remote_snapshots

        # _zfs_snap command redirects stderr into stdout and self.msg is always added into success result object
        self.msg = self._create_snapshot(snapshot, '%s=%s' % (self.NAME_PROPERTY, name), fsfreeze=fsfreeze, remote=True)
        self.last_snapshot = snapshot
        self._backup_dataset(snapshot, destination, incr_snapshot=incr_snap)
        backup_snapshot = build_snapshot(destination, snap_name)

        # From now on everything we do must _not_ raise an exception
        try:
            backup_snapshot_size = long_int(self._get_dataset_property(backup_snapshot, 'written'))
        except CmdError:
            backup_snapshot_size = 0

        if incr_snap:  # Remove old snapshot used for incremental backup
            try:
                self._destroy_dataset(incr_snap, remote=True)
            except CmdError:
                pass
            else:
                # noinspection PyUnboundLocalVariable
                self.deleted_last_snapshot_names.append(most_recent_snapshot)
        else:
            # Set readonly property on destination dataset
            self._set_dataset_property(destination, 'readonly', 'on')

        return {
            'backup_snapshot': backup_snapshot,
            'backup_snapshot_size': backup_snapshot_size,
            'update_snapshots': self.update_snapshots,
            'last_snapshot_name': get_snap_name(self.last_snapshot),
            'deleted_last_snapshot_names': self.deleted_last_snapshot_names,
            'metadata_file': self.metadata_file,
        }

    def ds_delete_cleanup(self, response):
        response['deleted_snapshots'] = self.deleted_snapshots
        response['update_snapshots'] = self._list_dataset_snapshot_size()
        response['deleted_last_snapshot_names'] = self.deleted_last_snapshot_names
        response['deleted_metadata_file'] = self.metadata_file

    @cmd_output
    def ds_delete(self, snapshots, metadata=None, last_snapshots=()):
        """Delete list of snapshots. This will also delete the whole dataset if deleting last snapshot on it!"""
        dataset_snapshots = defaultdict(list)
        current_snapshots = {}
        self.deleted_snapshots = deleted_snapshots = []
        self.affected_datasets = affected_datasets = []

        for snap in snapshots:  # Prepare {dataset: [snapshots]} map
            dataset_snapshots[get_snap_dataset(snap)].append(snap)

        for ds in dataset_snapshots:  # Get list of current backups on affected datasets
            current_snapshots[ds] = set(self._list_dataset_snapshots(ds))

        for ds, snaps in dataset_snapshots.items():
            ds_snapshots = current_snapshots[ds]
            snap_names = ','.join([get_snap_name(snap) for snap in snaps if snap in ds_snapshots])
            keep_dataset = bool(ds_snapshots.difference(snaps))  # Are there any snapshots left after removing snaps?

            if snap_names:
                if keep_dataset:
                    dataset = build_snapshot(ds, snap_names)
                    force = False
                else:
                    dataset = ds
                    force = True  # Destroy whole dataset, because there are no snapshots left

                # In case this would fail the cleanup method will add deleted snapshots list into the response
                self._destroy_dataset(dataset, force=force)

                deleted_snapshots.extend(snaps)

                if keep_dataset:
                    affected_datasets.append(ds)

        if metadata:
            # remove metadata file only at successful snapshot removal
            self._remove_json_metadata_file(metadata)  # Silent operation

        if last_snapshots:
            deleted_last_snapshot_names = [get_snap_name(snap) for snap in last_snapshots]
            remote_snapshots = build_snapshot(get_snap_dataset(last_snapshots[0]),
                                              ','.join(deleted_last_snapshot_names))

            try:
                self._destroy_dataset(remote_snapshots, remote=True)
            except CmdError:
                pass
            else:
                self.deleted_last_snapshot_names = deleted_last_snapshot_names

        return {
            'deleted_snapshots': deleted_snapshots,
            'update_snapshots': self._list_dataset_snapshot_size(),
            'deleted_last_snapshot_names': self.deleted_last_snapshot_names,
            'deleted_metadata_file': self.metadata_file
        }

    @cmd_output
    def ds_restore(self, snapshot, destination):
        """Restore source snapshot into target dataset (possibly on another host)"""
        self._check_dataset(snapshot)
        self._check_host()
        dest_backup = self._backup_and_create_empty_dataset(destination, remote=True)

        try:
            self._restore_dataset(snapshot, destination)  # Send/recv
            # Get all child datasets back to dest
            self._rename_dataset_children(dest_backup, destination, set_zoned=self.filesystem, remote=True)
        except CmdError:
            # Recover backed up destination, because send/recv failed
            self._destroy_dataset(destination, force=True, remote=True)  # Destroy the new dataset
            self._rename_dataset(dest_backup, destination, set_zoned=self.zoned, remote=True)  # Rollback

            if self.filesystem:  # Return zoned attribute to child datasets
                self._set_dataset_property(destination, 'zoned', 'on', children=True, remote=True)

            raise  # Re-raise exception
        else:
            # The temporary backup is not need any more
            self._destroy_dataset(dest_backup, force=True, remote=True)
            # There should be one snapshot on destination after successful restore
            try:
                self._destroy_dataset(switch_snap_dataset(snapshot, destination), remote=True)
            except CmdError:
                pass

        return {}

    @cmd_output
    def file_create(self, source, filename, metadata=None, json=None, fsfreeze=None):
        backup_dir = os.path.abspath(os.path.join(os.path.dirname(filename), '..', '..'))
        self._check_dir(backup_dir)  # Check parent/backup directory (zones/backups/file)
        self._check_host()
        filename = os.path.abspath(filename)
        self._create_backup_dir(os.path.dirname(filename))

        if metadata and json:
            # Create metadata file first, if it fails we dont need to create backup.
            self._store_json_metadata_to_file(metadata, json)

        try:
            self._backup_to_file(source, filename, fsfreeze=fsfreeze)
            size = self._get_file_size(filename)
            checksum = self._get_file_checksum(filename)
        except Exception:
            self._delete_file_silent(filename)
            if self.metadata_file:
                self._remove_json_metadata_file(metadata)  # Silent operation
            raise  # Re-raise error

        return {
            'file': filename,
            'size': size,
            'checksum': checksum,
            'metadata_file': self.metadata_file,
        }

    def file_delete_cleanup(self, response):
        response['deleted_files'] = self.deleted_files
        response['deleted_metadata_file'] = self.metadata_file

    @cmd_output
    def file_delete(self, filenames, metadata=None):
        self.deleted_files = deleted_files = []

        for f in filenames:
            f = os.path.abspath(f)
            self._delete_file(f)
            deleted_files.append(f)

        if metadata:
            self._remove_json_metadata_file(metadata)  # Silent operation

        return {
            'deleted_files': deleted_files,
            'deleted_metadata_file': self.metadata_file
        }

    @cmd_output
    def file_restore(self, destination, filename, checksum):
        self._check_file(filename)
        self._check_host()

        if checksum != self._get_file_checksum(filename):
            raise CmdError(self.ERR_FILE_CHECK, 'Checksum mismatch')

        dest_backup = self._backup_and_create_empty_dataset(destination, remote=True)

        try:
            self._restore_file(filename, destination)  # Send/recv
            # Get all child datasets back to dest
            self._rename_dataset_children(dest_backup, destination, set_zoned=self.filesystem, remote=True)
        except CmdError:
            # Recover backed up destination, because send/recv failed
            self._destroy_dataset(destination, force=True, remote=True)  # Destroy the new dataset
            self._rename_dataset(dest_backup, destination, set_zoned=self.zoned, remote=True)  # Rollback

            if self.filesystem:  # Return zoned attribute to child datasets
                self._set_dataset_property(destination, 'zoned', 'on', children=True, remote=True)

            raise  # Re-raise exception
        else:
            # The temporary backup is not need any more
            self._destroy_dataset(dest_backup, force=True, remote=True)
            # There should be one snapshot on destination after successful restore
            try:
                self._destroy_all_snapshots(destination, remote=True)
            except CmdError:
                pass

        return {}
