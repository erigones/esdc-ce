from __future__ import absolute_import

import os
from logging import getLogger
from subprocess import PIPE

from psutil import Popen
from celery.worker.control import Panel

from que import Q_FAST, Q_MGMT
from que.erigonesd import cq
from que.utils import generate_internal_task_id, log_task_callback, fetch_node_uuid, read_file
from que.tasks import execute_sysinfo
from que.exceptions import NodeError

ERIGONES_TASK_USER = cq.conf.ERIGONES_TASK_USER
ERIGONES_UPDATE_SCRIPT = cq.conf.ERIGONES_UPDATE_SCRIPT
SYSINFO_TASK = cq.conf.ERIGONES_NODE_SYSINFO_TASK
STATUS_CHECK_TASK = cq.conf.ERIGONES_NODE_STATUS_CHECK_TASK
MGMT_STARTUP_TASK = cq.conf.ERIGONES_MGMT_STARTUP_TASK

logger = getLogger(__name__)


# noinspection PyUnusedLocal
def task_revoked_handler(sender, request, terminated, signum, expired, **kwargs):
    """
    Revoked task handle.
    """
    if getattr(request, 'erigonesd_knows', False):
        logger.info('Task %s[%s] in revoked_handler :: Already running - skipping', sender.name, request.id)
        return

    setattr(request, 'erigonesd_knows', True)
    task_id = request.id

    # Reason displayed in result
    if terminated:
        detail = 'terminated (%s)' % signum
    elif expired:
        detail = 'expired'
    else:
        detail = 'revoked'

    log_task_callback(task_id, detail=detail, sender_name=sender.name)


def node_worker_start(sender):
    """
    Node worker startup handler.
    """
    worker = sender.split('@')

    if worker[0].startswith(Q_FAST):
        queue = '%s.%s' % (Q_FAST, worker[1])

        try:
            node_uuid = fetch_node_uuid()
        except NodeError as exc:
            logger.exception(exc)
            return

        tid, err = execute_sysinfo(ERIGONES_TASK_USER, ERIGONES_TASK_USER, queue=queue, node_uuid=node_uuid,
                                   initial=True)
        if err:
            logger.error('Error creating internal %s task: %s in %s queue', SYSINFO_TASK, err, queue)
        else:
            logger.warning('Created internal %s task %s in %s queue', SYSINFO_TASK, tid, queue)


# noinspection PyUnusedLocal
def mgmt_worker_start(sender):
    """
    Mgmt worker startup handler.
    """
    mgmt_startup_task_id = generate_internal_task_id()
    cq.send_task(MGMT_STARTUP_TASK, args=(mgmt_startup_task_id,), task_id=mgmt_startup_task_id, queue=Q_MGMT)
    status_check_task_id = generate_internal_task_id()
    cq.send_task(STATUS_CHECK_TASK, args=(status_check_task_id,), task_id=status_check_task_id, queue=Q_MGMT)


def worker_start(worker_hostname):
    """
    Called after the worker starts (via celery signal in que.tasks).
    """
    if worker_hostname.startswith(Q_MGMT + '@'):
        mgmt_worker_start(worker_hostname)
    else:
        node_worker_start(worker_hostname)


def _execute(cmd, stdin=None):
    """Run command and return output"""
    logger.warn('Running command (panel): %s', cmd)  # Warning level because we want to see this in logs
    proc = Popen(cmd, bufsize=0, close_fds=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
    stdout, stderr = proc.communicate(input=stdin)

    return {
        'returncode': proc.returncode,
        'stdout': stdout,
        'stderr': stderr,
    }


# noinspection PyUnusedLocal
def update_command(version, key=None, cert=None, sudo=False):
    """Call update script"""
    from core import settings

    ssl_key_file = settings.UPDATE_KEY_FILE
    ssl_cert_file = settings.UPDATE_CERT_FILE
    update_script = os.path.join(settings.PROJECT_DIR, ERIGONES_UPDATE_SCRIPT)
    cmd = [update_script, version]

    if sudo:
        cmd.insert(0, 'sudo')

    if key:

        try:
            with open(ssl_key_file, 'w+') as f:
                f.write(key)
        except IOError as err:
            logger.error('Error writing private key to file %s (%s)', ssl_key_file, err)

    # this serves double purpose to check if file was properly written
    # and to check if UPDATE_KEY_FILE exists if cert param was None
    if os.path.isfile(ssl_key_file):
        cmd.append(ssl_key_file)

    if cert:

        try:
            with open(ssl_cert_file, 'w+') as f:
                f.write(cert)
        except IOError as err:
            logger.error('Error writing private cert to file %s (%s)', ssl_cert_file, err)

    # this serves double purpose to check if file was properly written
    # and to check if UPDATE_CERT_FILE exists if cert param was None
    if os.path.isfile(ssl_cert_file):
        cmd.append(ssl_cert_file)

    return _execute(cmd)


# noinspection PyUnusedLocal
@Panel.register
def execute(state, cmd=None, stdin=None):
    """Execute a command on compute node"""
    assert cmd
    return _execute(cmd, stdin=stdin)


# noinspection PyUnusedLocal
@Panel.register
def system_update(state, version=None, key=None, cert=None):
    """Panel command that is simple wrapper around update_command performing update"""
    assert version
    return update_command(version, key=key, cert=cert)


# noinspection PyUnusedLocal
@Panel.register
def system_version(state):
    from core.utils import get_version
    return get_version()


# noinspection PyUnusedLocal
@Panel.register
def system_read_logs(state, log_files):
    """Function passed to worker (executed on a node) collecting logs"""
    from core import settings

    log_files_result = {}
    log_path = settings.LOGDIR

    for log in log_files:
        abs_path_name = os.path.join(log_path, log)

        try:
            with open(abs_path_name) as f:
                log_files_result[log] = read_file(f)
        except IOError as exc:
            logger.error('Error retrieving log file %s (%s)', abs_path_name, exc)
            # return an empty string for the log file which raised the exception
            log_files_result[log] = None

    return log_files_result
