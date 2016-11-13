from .cmd import CmdError, Cmd


def get_snap_name(snapshot):
    return snapshot.split('@')[-1]


def get_snap_dataset(snapshot):
    return snapshot.split('@')[0]


def build_snapshot(dataset, snapshot_name):
    return '%s@%s' % (dataset, snapshot_name)


def switch_snap_dataset(snapshot, new_dataset):
    snap = snapshot.split('@')
    snap[0] = new_dataset

    return '@'.join(snap)


class ZFSCmd(Cmd):
    """
    Cmd class extended with common ZFS helper commands.
    """
    def _get_dataset_property(self, dataset, attr, remote=False):
        return self._run_cmd('_zfs_dataset_property', dataset, attr, remote=remote)

    def _set_dataset_property(self, dataset, name, value, children=False, remote=False):
        if children:
            cmd = '_zfs_set_dataset_property_children'
        else:
            cmd = '_zfs_set_dataset_property'

        return self._run_cmd(cmd, dataset, name, value, remote=remote)

    def _clear_dataset_property(self, dataset, name, remote=False):
        return self._run_cmd('_zfs_clear_dataset_property', dataset, name, remote=remote)

    def _get_dataset_properties(self, dataset, attrs, remote=False):
        props = self._run_cmd('_zfs_dataset_properties', dataset, ','.join(attrs), remote=remote).split('\n')
        properties = [map(str.strip, prop.split()) for prop in props]

        def zero_to_none(x):
            return 'none' if x == '0' else x

        # Remove dash values and change 0 to 'none'
        return {k: zero_to_none(v) for k, v in properties if v != '-'}

    def _set_dataset_properties(self, dataset, properties, remote=False):
        res = {}

        for name, value in properties.items():
            res[name] = self._set_dataset_property(dataset, name, value, remote=remote)

        return res

    def _create_snapshot(self, snapshot, metadata=None, fsfreeze=None, remote=False):
        cmd = ['_zfs_snap', snapshot, metadata or 'null']

        if fsfreeze:
            cmd.append(fsfreeze)

        return self._run_cmd(*cmd, remote=remote, stderr_to_stdout=True)

    def _destroy_dataset(self, dataset, force=False, remote=False):
        cmd = ['_zfs_destroy', dataset]

        if force:
            cmd.append('true')

        return self._run_cmd(*cmd, remote=remote)

    def _dataset_exists(self, dataset, remote=False):
        try:
            self._run_cmd('_zfs_dataset_exists', dataset, remote=remote)
        except CmdError as e:
            if 'does not exist' in e.msg:
                return False
            raise e
        else:
            return True

    def _mount_dataset(self, dataset, remote=False):
        return self._run_cmd('_zfs_mount', dataset, remote=remote)

    def _unmount_dataset(self, dataset, force=False, remote=False):
        cmd = ['_zfs_unmount', dataset]

        if force:
            cmd.append('true')

        return self._run_cmd(*cmd, remote=remote)
