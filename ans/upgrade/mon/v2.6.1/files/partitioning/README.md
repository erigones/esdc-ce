# Zabbix PostgreSQL scripts

Scripts for partitioning the Zabbix database on PostgreSQL.

__WARNINGS:__

* PostgreSQL partitioning is not supported by Zabbix SIA technical support
* Changing partition configuration on existing datasets requires a great deal
  of care and is not recommended for newbies
* The Zabbix server and web server should not be running when making changes

These scripts cater for partitioning any Zabbix tables that include the `clock`
column.

Partitioning is recommended for large tables such as `history*`, `trends*` and `events` where the data size might exceed total physical RAM. When selecting a
partitioning interval, try find a balance between minimising the number of
partitions (e.g. use yearly or monthly), preventing empty partitions and
preventing partition size from exceeding total physical RAM.

Please read all code and comments in the scripts before running on a production
dataset.

### Repair `c_event_recovery_1` on Zabbix 3.2+

The following is only valid if your `events` table is partitioned prior to
upgrading to Zabbix v3.2+.

See [ZBX-11257](https://support.zabbix.com/browse/ZBX-11257).

* Stop the Zabbix server when you see the following log entry:
  ```
  query failed: [0] PGRES_FATAL_ERROR:ERROR:  insert or update on table "event_recovery" violates foreign key constraint "c_event_recovery_1"
  ```

* Run the repair script:
  ```
  $ psql -U zabbix -d zabbix < repair-zabbix-3.2.0.sql
  ```

* Restart Zabbix server to resume database upgrade
* Email author gratitude or grudge

### Create partition schema

Partitioning results in a large number of tables - ever increasing over time.
To simplify management, these tables should be isolated from standard Zabbix
tables using a separate schema. By default, tables will be stored in the
`public` schema. The scripts in this repo assume all partition tables will be
stored instead in a schema named `partitions`, though this can be configured
using the `schema_name` parameter of most script functions.

Create the schema with the following SQL query:

```sql
-- replace 'zabbix' with the name of your zabbix database role
CREATE SCHEMA partitions AUTHORIZATION zabbix;
```

### Install partitioning functions

    $ psql -U zabbix -d zabbix < bootstrap.sql


### Create partitions for a table

```sql
-- create partitions for 14 days for the history table
SELECT zbx_provision_partitions('history', 'day', 14);
```

### Create routing trigger for INSERTS

```sql
-- add trigger to the history table
SELECT zbx_provision_partitions('history', 'day', 14);
```

### Unpartition a table

```sql
-- remove partition configuration, migrate data into parent table and
-- drop child partitions for 'history' table
SELECT zbx_deprovision_partitions('history');
```


### Optimize superceded partition

```sql
-- add constraint to old 'events' partition by min and max 'eventid'
SELECT zbx_constrain_partition('events_2015', 'eventid');
```


### Drop old partitions

```sql
-- drop history partitions older than Jan 1, 2015
SELECT zbx_drop_old_partitions('history', '2015-01-01'::TIMESTAMP);
```


## License

Copyright (c) 2016 Ryan Armstrong

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
