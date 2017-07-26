#!/usr/bin/python
#
# Zabbix PostgreSQL partitioning helper script
#
# USAGE
#   Use `zbx-partitions.py init` only once at the beginning to initialize partitioning
#   Add `zbx-partitions.py` to crontab (daily) to periodically create and cleanup partitions
#   Disable Housekeeper in zabbix_server.conf (HousekeepingFrequency=0)
#

from __future__ import print_function
from datetime import datetime, timedelta
import sys
import psycopg2

tables = {
    'history': ('day', 7),
    'history_uint': ('day', 7),
    'history_str': ('day', 7),
    'history_log': ('day', 7),
    'history_text': ('day', 7),
    'trends': ('month', 12),
    'trends_uint': ('month', 12),
}

# change these settings
db_user = 'zabbix'
db_pw = 'zabbix'
db_name = 'zabbix'
db_host = 'localhost'
#####

debug = sys.argv[-1] in ('-d', '-v', '--debug', '--verbose')
init = len(sys.argv) > 1 and sys.argv[1] == 'init'


def execute_sql(query, params):
    if debug:
        print('* Running: %s' % (query % params))

    db_cursor.execute(query, params)

    if debug:
	for notice in db_connection.notices:
	    print(notice.strip())
	del db_connection.notices[:]
        print('***')


def get_days(partition_by):
    if partition_by == 'month':
        days = 365/12
    elif partition_by == 'year':
        days = 365
    elif partition_by == 'day':
        days = 1
    else:
        raise ValueError('Invalid partitioning schema: %s' % partition_by)

    return days


db_connection = psycopg2.connect(database=db_name, user=db_user, password=db_pw, host=db_host)
db_cursor = db_connection.cursor()

# Create partitions
for table_name, options in tables.items():
    execute_sql('''SELECT zbx_provision_partitions(%s, %s, %s)''', (table_name, options[0], options[1]))

if init:
    # Enable trigger
    for table_name, options in tables.items():
        execute_sql('''SELECT zbx_enable_partitions(%s, %s)''', (table_name, options[0]))
else:
    now = datetime.now()
    # Cleanup old partitions
    for table_name, options in tables.items():
        cutoff = now - timedelta(days=get_days(options[0]) * options[1])
        execute_sql('''SELECT zbx_drop_old_partitions(%s, %s)''', (table_name, cutoff))

db_connection.commit()
db_cursor.close()
db_connection.close()
