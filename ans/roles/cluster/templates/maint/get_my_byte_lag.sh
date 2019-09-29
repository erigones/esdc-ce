#!/bin/sh

if [ $(whoami) != "postgres" ]; then 
	echo "Please run this script as user postgres!"
	exit 1
fi

DBMASTER_IP="{{ cluster_vip }}"
DBPORT="{{ postgres_port }}"
PGDATA="{{ pgdata }}"
DBVERSION="{{ pgversion }}"
REPL_USER="{{ pg_repl_user }}"

EXTENDED_QUERY="SELECT pg_xlog_location_diff(pg_stat_replication.sent_location, pg_stat_replication.replay_location) AS byte_lag FROM pg_stat_replication WHERE application_name='$(hostname -s)'"

psql -Aqtc "$EXTENDED_QUERY" -h "$DBMASTER_IP" -U "$REPL_USER" postgres

