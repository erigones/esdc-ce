#!/usr/bin/env python
from __future__ import absolute_import

import os
import sys

if 'gevent' in sys.argv:
    from gevent import monkey
    monkey.patch_all()
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
elif 'eventlet' in sys.argv:
    # noinspection PyUnresolvedReferences
    import eventlet
    eventlet.monkey_patch()
    # Eventlet supports Psycopg out-of-the-box

# noinspection PyPep8
from celery import Celery

# noinspection PyPep8
from que.bootsteps import ESDCDaemon, FastDaemon, MgmtDaemon

# Set default configuration module name
os.environ.setdefault('CELERY_CONFIG_MODULE', 'core.celery.config')
# Create celery queue (cq) application
cq = Celery()
cq.config_from_envvar('CELERY_CONFIG_MODULE')

cq.steps['worker'].add(ESDCDaemon)
cq.steps['consumer'].add(FastDaemon)
cq.steps['consumer'].add(MgmtDaemon)

if __name__ == '__main__':
    cq.start()
