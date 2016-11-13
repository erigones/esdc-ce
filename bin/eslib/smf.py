from .cmd import CmdError, Cmd


class SMFCmd(Cmd):
    """
    Cmd class extended with common SMF helper commands.
    """
    def _service_status(self, fmri, columns=('state',), remote=False):
        return self._run_cmd('_service_status', fmri, ','.join(columns), stderr_to_stdout=True, remote=remote)

    def _service_enable(self, fmri, remote=False):
        return self._run_cmd('_service_enable', fmri, remote=remote)

    def _service_disable(self, fmri, remote=False):
        return self._run_cmd('_service_disable', fmri, remote=remote)

    def _service_restart(self, fmri, remote=False):
        return self._run_cmd('_service_restart', fmri, remote=remote)

    def _service_validate(self, manifest_file, remote=False):
        return self._run_cmd('_service_validate', manifest_file, remote=remote)

    def _service_import(self, fmri, manifest_file, remote=False):
        return self._run_cmd('_service_import', fmri, manifest_file, remote=remote)

    def _service_export(self, fmri, remote=False):
        return self._run_cmd('_service_export', fmri, remote=remote)

    def _service_delete(self, fmri, remote=False):
        return self._run_cmd('_service_delete', fmri, remote=remote)

    def _service_save(self, fmri, remote=False):
        return self._run_cmd('_service_save', fmri, remote=remote)

    def _service_exists(self, fmri, remote=False):
        try:
            self._service_export(fmri, remote=remote)
        except CmdError as exc:
            if "doesn't match any service" in exc.msg:
                return False
            else:
                raise exc
        else:
            return True

    def _service_instance_import(self, fmri, manifest_file, remote=False):
        return self._run_cmd('_service_instance_import', fmri, manifest_file, remote=remote)

    def _service_instance_delete(self, fmri, name, remote=False):
        return self._run_cmd('_service_instance_delete', fmri, name, remote=remote)

    def _service_instance_exists(self, fmri, remote=False):
        try:
            self._service_status(fmri, remote=remote)
        except CmdError as exc:
            if "doesn't match any instances" in exc.msg:
                return False
            else:
                raise exc
        else:
            return True
