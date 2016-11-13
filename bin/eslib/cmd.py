from __future__ import print_function
from subprocess import PIPE, STDOUT
from functools import wraps, partial
from time import time
from psutil import Popen
import simplejson as json  # required because it can handle namedtuples as dicts
import os
import sys
import signal

ERR_SIGTERM = 215
GOT_SIGTERM = False


def execute(cmd, stderr_to_stdout=False, stdin=None):
    """Execute a command in the shell and return a tuple (rc, stdout, stderr)"""
    if stderr_to_stdout:
        stderr = STDOUT
    else:
        stderr = PIPE

    if stdin is None:
        _stdin = None
    else:
        _stdin = PIPE

    p = Popen(cmd, close_fds=True, stdin=_stdin, stdout=PIPE, stderr=stderr, preexec_fn=os.setsid)
    stdout, stderr = p.communicate(input=stdin)

    return p.returncode, stdout, stderr


def get_timestamp():
    """Current unix epoch time (UTC)"""
    return int(time())


class CmdError(Exception):
    """
    Danube Cloud command error exception.
    """
    def __init__(self, rc, msg, **kwargs):
        self.rc = rc
        self.msg = msg
        self.success = False
        self.__dict__.update(kwargs)
        super(CmdError, self).__init__(msg)

    def __str__(self):
        return 'Error %s: %s' % (self.rc, self.msg)

    def cmd_output(self):
        return self.__dict__

    @staticmethod
    def exception_to_string(exc, debug=False):
        if debug:
            import traceback
            print('Exception occurred:', file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

        return '%s: %s' % (exc.__class__.__name__, exc)


class Cmd(object):
    """
    Danube Cloud command base class.
    """
    CMD = NotImplemented  # Set in descendant class (must be a tuple)

    OK = 0
    ERR_HOST_CHECK = 3
    ERR_UNKNOWN = 99

    msg = None  # Added into output if set
    _time_started = 0

    def __init__(self, host=None, verbose=False, **kwargs):
        self.host = host
        self.verbose = verbose
        self.__dict__.update(kwargs)
        self._time_started = get_timestamp()

    def log(self, msg):
        if self.verbose:
            print('[%s] %s' % (get_timestamp(), msg), file=sys.stderr)

    def _run_local(self, cmd, **kwargs):
        cmd = self.CMD + cmd
        self.log('Running command: %s' % ' '.join(cmd))  # The cmd tuple must contain only strings!
        rc, stdout, stderr = execute(cmd, **kwargs)
        self.log('Return code: %d' % rc)

        if rc != 0:
            raise CmdError(rc, stderr or stdout)

        return stdout.strip()

    def _run_remote(self, cmd, **kwargs):
        if self.host:
            cmd = ('run_ssh', 'root@%s' % self.host) + self.CMD + cmd

        return self._run_local(cmd, **kwargs)

    def _run_cmd(self, *cmd, **kwargs):
        if kwargs.pop('remote', False):
            return self._run_remote(cmd, **kwargs)
        else:
            return self._run_local(cmd, **kwargs)

    def _check_host(self, hostname=False):
        if self.host:
            if hostname:
                test_cmd = 'test_ssh_hostname'
            else:
                test_cmd = 'test_ssh'

            try:
                return self._run_local((test_cmd, self.host))
            except CmdError as e:
                raise CmdError(self.ERR_HOST_CHECK, 'Remote host is unreachable (%s)' % e.msg or e.rc)

    def _get_hostname(self, remote=False):
        return self._run_cmd('get_hostname', remote=remote)

    def add_timestamps(self, output_dict):
        """Add timestamp parameters into final output dictionary"""
        time_ended = get_timestamp()

        output_dict.update({
            'time_started': self._time_started,
            'time_ended': time_ended,
            'time_elapsed': time_ended - self._time_started,
        })

    def cleanup(self, action, response):
        """Emergency rollback - run action_cleanup() method"""
        fun = getattr(self, '%s_cleanup' % action, None)

        if fun:
            self.log('Running cleanup for "%s" action' % action)
            fun(response)

    @staticmethod
    def print_output(output_dict):
        print(json.dumps(output_dict, indent=4))

    @classmethod
    def output_and_exit(cls, output_dict):
        cls.print_output(output_dict)
        sys.exit(output_dict['rc'])


def cmd_error(obj, fun_name, exc):
    """Exception handler used in cmd_output decorator"""
    if exc is None or not isinstance(exc, CmdError):
        exc = CmdError(Cmd.ERR_UNKNOWN, CmdError.exception_to_string(exc, debug=obj.verbose))

    response = exc.cmd_output()

    try:
        obj.cleanup(fun_name, response)
    except Exception as e:
        obj.log('Cleanup failed! (%s)' % CmdError.exception_to_string(e, debug=obj.verbose))

    return response


# noinspection PyUnusedLocal
def _cmd_sigterm_handler(obj, fun_name, signum, frame):
    """Signal 15 error handler used in cmd_output decorator"""
    global GOT_SIGTERM

    obj.log('Received signal #%s in %s()' % (signum, fun_name))

    if GOT_SIGTERM:
        obj.log('Ignoring signal #%s, because the signal handler is already running' % signum)
    else:
        GOT_SIGTERM = True
        raise CmdError(ERR_SIGTERM, 'Terminated by signal #%s in %s()' % (signum, fun_name))


def cmd_output(fun):
    """Decorator for creating common Danube Cloud command output"""
    @wraps(fun)
    def wrap(obj, *args, **kwargs):
        signal.signal(signal.SIGTERM, partial(_cmd_sigterm_handler, obj, fun.__name__))

        try:
            response = fun(obj, *args, **kwargs)

            if response is None:
                response = {}

            response['rc'] = Cmd.OK
            response['success'] = True

            if obj.msg:
                response['msg'] = obj.msg

        except (Exception, KeyboardInterrupt) as ex:
            response = cmd_error(obj, fun.__name__, ex)

        obj.add_timestamps(response)

        return response
    return wrap
