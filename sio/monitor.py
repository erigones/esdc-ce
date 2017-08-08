from __future__ import print_function

from blinker import signal
from gevent import sleep

from que.erigonesd import cq
from que.utils import user_owner_dc_ids_from_task_id
from gui.models import User
from api.exceptions import OPERATIONAL_ERRORS


def que_monitor(app, _info=print, _debug=print):
    """
    Real-time event processing loop.
    """
    def _log(fun, msg, *args):
        fun('[sio.monitor] ' + msg % args)

    def log(msg, *args):
        _log(_info, msg, *args)

    def debug(msg, *args):
        _log(_debug, msg, *args)

    log('Starting dedicated que event monitor')
    internal_id = app.conf.ERIGONES_TASK_USER

    def _announce_task(event, event_status):
        task_id = event['uuid']
        user_id, owner_id, dc_id = user_owner_dc_ids_from_task_id(task_id)

        if owner_id == internal_id:
            return  # probably beat task

        if event.get('queue', None) == 'mgmt':
            return  # sent task on mgmt

        if event.get('direct', None):
            # Send signal to ObjectOwner only
            users = (int(owner_id),)
        else:
            # Send signal to all affected users
            users = User.get_super_admin_ids()  # SuperAdmins
            users.update(User.get_dc_admin_ids(dc_id=dc_id))  # DcAdmins
            users.add(int(user_id))  # TaskCreator
            users.add(int(owner_id))  # ObjectOwner

        debug('Sending signal for %s task %s to %s', event_status, task_id, users)

        # Signal!
        for i in users:
            new_task = signal('task-for-%s' % i)
            new_task.send(event, task_id=task_id, event_status=event_status)

    def announce_fail_tasks(event):
        _announce_task(event, 'failed')

    def announce_done_tasks(event):
        _announce_task(event, 'succeeded')

    def announce_sent_tasks(event):
        _announce_task(event, 'sent')

    def announce_event_tasks(event):
        _announce_task(event, 'event')

    # Here we go
    with app.connection() as conn:
        recv = app.events.Receiver(conn, handlers={
            # The sent signal (task-sent) is disabled in celery and was substituted by our
            # custom task-created signal emitted from TaskResponse.
            'task-created': announce_sent_tasks,
            'task-failed': announce_fail_tasks,
            'task-succeeded': announce_done_tasks,
            'task-event': announce_event_tasks,
            # The revoked signal (task-revoked) is not needed because a success logtask
            # executed on mgmt will follow every revoke on node.
        })
        recv.capture(limit=None, timeout=None, wakeup=False)


# noinspection PyUnusedLocal
def que_monitor_loop(server, worker):
    log = worker.log

    while True:
        try:
            que_monitor(cq, _info=log.info, _debug=log.debug)
        except OPERATIONAL_ERRORS as ex:
            log.exception(ex)
            log.critical('Dedicated que event monitor terminated. Closing DB connection and restarting in 1 second...')
            from django import db
            db.close_old_connections()
        except Exception as ex:
            log.exception(ex)
            log.critical('Dedicated que event monitor terminated. Restarting in 5 seconds...')
            sleep(5)


if __name__ == '__main__':
    que_monitor(cq)
