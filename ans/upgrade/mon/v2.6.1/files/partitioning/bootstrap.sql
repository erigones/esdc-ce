--------------------------------------------------------------------------------
--                Zabbix Partitioning functions for PostgreSQL                --
--------------------------------------------------------------------------------
--
-- Original source: https://github.com/cavaliercoder/zabbix-pgsql-partitioning/
--
-- This script installs functions to a Zabbix PostgreSQL database to assist in
-- managing partitions.
--
-- WARNING:	For safety, only call functions from this script when the Zabbix
-- 			server is not running. This will ensure new records do not leak into
-- 			incorrect table while partitioning schema changes are in process.
--
-- WARNING:	This script assumes all partitions are managed by this script. Any
-- 			configurations changes made outside these functions may result in
-- 			data loss.
--

--
-- View to show all partitions and their parents
--
CREATE OR REPLACE VIEW zbx_partitions AS
	SELECT
		inhparent		AS parent_oid
		, pn.nspname	AS parent_nspname
		, pc.relname	AS parent_relname
		, inhrelid		AS child_oid
		, cn.nspname	AS child_nspname
		, cc.relname	AS child_relname
	FROM pg_inherits i
	JOIN pg_class pc 		ON i.inhparent = pc.oid
	JOIN pg_namespace pn	ON pc.relnamespace = pn.oid
	JOIN pg_class cc		ON i.inhrelid = cc.oid
	JOIN pg_namespace cn	ON cc.relnamespace = cn.oid
	ORDER BY cc.relname ASC;

--
-- Return the time format used to suffix child partitions when partitioning by
-- partition_by.
--
-- partition_by:	period per partition [day|month|year] (default: month)
--
CREATE OR REPLACE FUNCTION zbx_time_format_by(
	partition_by	TEXT
) RETURNS varchar AS $$
	DECLARE
		time_format	TEXT;
	BEGIN
		CASE partition_by
			WHEN 'day'		THEN time_format := 'YYYY_MM_DD';
			WHEN 'month'	THEN time_format := 'YYYY_MM';
			WHEN 'year'		THEN time_format := 'YYYY';
			ELSE RAISE 'Unsupported partition_by value: %', partition_by;
		END CASE;

		RETURN time_format;
	END;
$$ LANGUAGE plpgsql;

--
-- Trigger function to route inserts from a parent table to the correct child
-- partition. This function is called on INSERT by any table that has been
-- partitioned with zbx_provision_partitions().
--
-- To prevent data loss the trigger will pass control back to the caller if any
-- exception occurs when routing to the child partition.
--
CREATE OR REPLACE FUNCTION zbx_route_insert_by_clock()
	RETURNS TRIGGER AS $$
	DECLARE
		schema_name TEXT;
		table_name	TEXT;
		time_format	TEXT;
	BEGIN
		-- trigger arguments
		schema_name	:= TG_ARGV[0];
		time_format	:= TG_ARGV[1];

		-- compute destination partition by appending NEW.clock to the original
		-- table name, formatted using time_format
		table_name := schema_name || '.' || TG_TABLE_NAME || '_'
			|| TO_CHAR(TO_TIMESTAMP(NEW.clock), time_format);

		BEGIN
			-- attempt insert
			EXECUTE 'INSERT INTO ' || table_name || ' SELECT ($1).*;' USING NEW;
			RETURN NULL;

		EXCEPTION WHEN OTHERS THEN
			-- pass control back on error
			RAISE WARNING 'Error inserting new record into %', table_name;
			RETURN NEW;
		END;
	END;
$$ LANGUAGE plpgsql;

--
-- Configure a table for partitioning by `clock` column and provision partitions
-- in advance.
--
-- table_name:		table to create child partitions for (e.g. history)
-- partition_by:	period per partition [day|month|year] (default: month)
-- count:			number of partitions to provision, starting from NOW() 
-- 					(default: 12)
-- schema_name:		target schema where partitions are stored
-- 					(default: partitions)
-- parent_schema_name: parent table schema name (default: public)
--
CREATE OR REPLACE FUNCTION zbx_provision_partitions(
	table_name		TEXT
	, partition_by	TEXT	DEFAULT 'month'
	, count			BIGINT	DEFAULT 12
	, schema_name	TEXT	DEFAULT 'partitions'
	, parent_schema_name	TEXT	DEFAULT 'public'
) RETURNS VOID AS $$
	DECLARE
		time_format			TEXT;
		time_interval		INTERVAL;
		start_date			INTEGER;
		end_date			INTEGER;
		new_table_name		TEXT;
		new_constraint_name	TEXT;
	BEGIN
		-- set time_format, used to format the partition suffix
		time_format := (SELECT zbx_time_format_by(partition_by));

		-- compute time interval for partition period
		time_interval := '1 ' || partition_by;

		-- create <count> new partitions
		FOR i IN 0..(count - 1) LOOP
			start_date			:= EXTRACT(EPOCH FROM DATE_TRUNC(partition_by, NOW() + (time_interval * i)));
			end_date			:= EXTRACT(EPOCH FROM DATE_TRUNC(partition_by, NOW() + (time_interval * (i + 1))));
			new_table_name		:= table_name || '_' || TO_CHAR(NOW() + (time_interval * i), time_format);
			new_constraint_name	:= new_table_name || '_clock';

			-- check if table exists
			BEGIN
				PERFORM (schema_name || '.' || new_table_name)::regclass;
				RAISE NOTICE 'partition already exist: %.%', schema_name, new_table_name; 

			EXCEPTION WHEN undefined_table THEN
				-- create missing table, copying schema from parent table
				EXECUTE 'CREATE TABLE ' || schema_name || '.' || new_table_name || ' (
					LIKE ' || parent_schema_name || '.' || table_name || '
						INCLUDING DEFAULTS
						INCLUDING CONSTRAINTS
						INCLUDING INDEXES
				) INHERITS (' || parent_schema_name || '.' || table_name || ');';

				-- add clock column constraint
				EXECUTE 'ALTER TABLE ' || schema_name || '.' || new_table_name
					|| ' ADD CONSTRAINT ' || new_constraint_name
					|| ' CHECK ( clock >= ' || start_date || ' AND clock < ' || end_date || ' );';				
			END;
		END LOOP;
	END;
$$ LANGUAGE plpgsql;

--
-- Adds a trigger, which routes INSERTS into a specific partition.
-- The partitions must exist in advance (zbx_provision_partitions).
--
-- table_name:		partitioned table to add triggers to (e.g. history)
-- partition_by:	period per partition [day|month|year] (default: month)
-- trigger_name:	name of the trigger to be dropped from the parent table
-- 					(default: {table_name}_insert)
-- schema_name:		target schema where partitions are stored
-- 					(default: partitions)
-- parent_schema_name: parent table schema name (default: public)
--
CREATE OR REPLACE FUNCTION zbx_enable_partitions(
	table_name		TEXT
	, partition_by	TEXT	DEFAULT 'month'
	, trigger_name	TEXT	DEFAULT ''
	, schema_name	TEXT	DEFAULT 'partitions'
	, parent_schema_name	TEXT	DEFAULT 'public'
) RETURNS VOID AS $$
	DECLARE
		time_format			TEXT;
		partition_name		TEXT;
	BEGIN
		-- set time_format, used to format the partition suffix
		time_format := (SELECT zbx_time_format_by(partition_by));

		-- default trigger name
		IF trigger_name = '' THEN
			trigger_name = table_name || '_insert';
		END IF;

		-- get partition name for the next check
		partition_name := table_name || '_' || TO_CHAR(NOW(), time_format);

		-- check if partition exists
		BEGIN
			PERFORM (schema_name || '.' || partition_name)::regclass;
		EXCEPTION WHEN undefined_table THEN
			RAISE 'Next partition %.% for table %.% does not exist!', schema_name, partition_name, parent_schema_name, table_name;
		END;

		-- trigger the routing function on insert to the parent table
		-- TODO: is there a race condition here if a row is inserted BEFORE the
		-- trigger is recreated? Rows could leak into the parent table.
		EXECUTE 'DROP TRIGGER IF EXISTS ' || QUOTE_IDENT(trigger_name) || ' ON ' || parent_schema_name || '.' || table_name || ';';
		EXECUTE 'CREATE TRIGGER ' || QUOTE_IDENT(trigger_name) || '
				BEFORE INSERT ON ' || parent_schema_name || '.' || table_name || '
				FOR EACH ROW EXECUTE PROCEDURE zbx_route_insert_by_clock(' || QUOTE_IDENT(schema_name) || ', ' || QUOTE_LITERAL(time_format) || ');';
	END;
$$ LANGUAGE plpgsql;

--
-- Remove partition configuration from a table by copying data from all child
-- partitions into the parent table, deleting the partitions and removing the
-- partitioning triggers.
-- 
-- WARNING: all insert triggers must be removed from the parent table to ensure
-- copied rows are inserted into the parent; not back into the child partitions.
--
-- You should probably stop the Zabbix server while running this function.
-- Otherwise new value are inserted into the parent table BEFORE the data is
-- copied from child tables. Data are then no longer sequential.
--
-- This function also assumes that all child partitions are ordered both
-- chronologically and alphanumerically so that data is copied in the correct
-- order.
-- 
-- All child tables are dropped!
--
-- table_name:			parent table name
-- trigger_name:		name of the trigger to be dropped from the parent table
-- 						(default: {table_name}_insert)
-- schema_name:			parent table schema name (default: public)
--
CREATE OR REPLACE FUNCTION zbx_deprovision_partitions(
	table_name		TEXT
	, trigger_name	TEXT	DEFAULT ''
	, schema_name	TEXT	DEFAULT 'public'
) RETURNS VOID AS $$
	DECLARE
		child		RECORD;
		ins_count	INTEGER DEFAULT 0;
	BEGIN
		-- default trigger name
		IF trigger_name = '' THEN
			trigger_name = table_name || '_insert';
		END IF;

		-- delete the insert trigger on the parent table
		BEGIN
			EXECUTE 'DROP TRIGGER ' || trigger_name || ' ON ' || schema_name || '.' || table_name || ' CASCADE;';
		EXCEPTION WHEN undefined_object THEN
			RAISE NOTICE 'Trigger % does not exist on %.%', trigger_name, schema_name, table_name;
		END;

		-- loop through child tables
		FOR child IN ( 
			SELECT *
			FROM zbx_partitions
			WHERE
				parent_relname = table_name
				AND parent_nspname = schema_name
		) LOOP
			-- copy content into parent table
			EXECUTE 'INSERT INTO ' || schema_name || '.' || table_name || ' SELECT * FROM ONLY ' || child.child_nspname || '.' || child.child_relname;
			GET DIAGNOSTICS ins_count := ROW_COUNT;
			
			-- drop partition
			EXECUTE 'DROP TABLE ' || child.child_nspname || '.' || child.child_relname || ';';

			-- notify
			RAISE NOTICE 'Copied % rows from %.%', ins_count, child.child_nspname, child.child_relname;
		END LOOP;

		-- update stats for parent table
		EXECUTE 'ANALYZE ' || schema_name || '.' || table_name || ';';
	END;
$$ LANGUAGE plpgsql;

--
-- Constrain a superceded child partition table by the minimum and maximum id.
--
-- Improves performance on lookups by ID by stopping old partitions from being
-- scanned for values that are out of range.
-- 
-- WARNING: Do no apply to a table that will still be appended to
--
-- To undo: 
--   `ALTER TABLE {table_name} DROP CONSTRAINT {table_name}_{column_name};`
--
-- table_name:	child table to constrain
-- column_name:	numeric ID column to constrain by
-- schema_name:	schema where child table exists (default: partitions)
--
CREATE OR REPLACE FUNCTION zbx_constrain_partition(
	table_name		TEXT
	, column_name	TEXT
	, schema_name	TEXT	DEFAULT 'partitions'
) RETURNS VOID AS $$
	DECLARE
		min_id				BIGINT DEFAULT 0;
		max_id				BIGINT DEFAULT 0;
		new_constraint_name	TEXT;
	BEGIN
		new_constraint_name := table_name || '_' || column_name;

		-- find minimum and maximum id
		EXECUTE 'SELECT MIN(' || column_name || '), MAX(' || column_name || ') FROM ONLY ' || schema_name || '.' || table_name || ';' INTO min_id, max_id;

		-- remove existing constraint
		EXECUTE 'ALTER TABLE ' || schema_name || '.' || table_name
			|| ' DROP CONSTRAINT IF EXISTS ' || new_constraint_name || ';';

		-- add constraint
		EXECUTE 'ALTER TABLE ' || schema_name || '.' || table_name
			|| ' ADD CONSTRAINT ' || new_constraint_name
			|| ' CHECK ( ' || column_name || ' >= ' || min_id || ' AND ' || column_name || ' <= ' || max_id || ' );';

		RAISE NOTICE 'Added constraint % ( % >= % <= % )', new_constraint_name, min_id, column_name, max_id;
	END;
$$ LANGUAGE plpgsql;

--
-- Drop old partitions for the given parent table.
-- 
-- The age of a partition is evaluated by parsing the timestamp suffix (e.g.
-- '..._2016_10_17'). If the upper bound timestamp (not the lower bound suffix)
-- of the partition is older than the given cutoff timestamp, the partition is
-- deleted.
-- 
-- The upperbound is computed by assuming that all partitions ending in '_YYYY'
-- contain one year of data, '_YYYY_MM' contains one month, '_YYYY_MM_DD'
-- contains one day, etc.
--
-- Partitions with an upper bound in the future are protected from being
-- dropped.
--
-- table_name:	parent table to drop partitions for
-- cutoff:		timestamp of the oldest partition to retain
-- schema_name:	schema where parent table exists (default: public)
--
CREATE OR REPLACE FUNCTION zbx_drop_old_partitions(
	table_name		TEXT
	, cutoff		TIMESTAMP WITH TIME ZONE
	, schema_name	TEXT	DEFAULT 'public'
) RETURNS VOID AS $$
	DECLARE
		child			RECORD;
		child_bound		TIMESTAMP;
		child_date		RECORD;
	BEGIN
		-- loop through each child partition
		FOR child IN ( 
			SELECT * FROM zbx_partitions
			WHERE
				parent_relname		= table_name
				AND parent_nspname	= schema_name
		) LOOP
			-- extract date component from partition suffix
			SELECT 
				SUBSTRING(child.child_relname FROM '\d{4}$')				AS by_year
				, SUBSTRING(child.child_relname FROM '\d{4}_\d{2}$')		AS by_month
				, SUBSTRING(child.child_relname FROM '\d{4}_\d{2}_\d{2}$')	AS by_day
			INTO child_date;

			-- calculate upper bound timestamp of partition
			IF child_date.by_day <> '' THEN
				child_bound := TO_TIMESTAMP(child_date.by_day, 'YYYY_MM_DD') + '1 day'::INTERVAL;
			ELSIF child_date.by_month <> '' THEN
				child_bound := TO_TIMESTAMP(child_date.by_month, 'YYYY_MM') + '1 month'::INTERVAL;
			ELSIF child_date.by_year <> '' THEN
				child_bound := TO_TIMESTAMP(child_date.by_year, 'YYYY') + '1 year'::INTERVAL;
			ELSE
				RAISE 'Unsupported partition date suffix: %.%', child.child_nspname, child.child_relname;
			END IF;

			-- protect current partition
			IF NOW() < child_bound THEN
				RAISE NOTICE 'Current timestamp is earlier than upper bound for partition %.%', child.child_nspname, child.child_relname;
			-- drop table if upper bound is older than cutoff date
			ELSIF child_bound <= cutoff THEN
				EXECUTE 'DROP TABLE ' || child.child_nspname || '.' || child.child_relname || ';';
				RAISE NOTICE 'Dropped partition: %.%', child.child_nspname, child.child_relname;
			ELSE
				RAISE NOTICE 'Ignoring partition %.%', child.child_nspname, child.child_relname;
			END IF;
		END LOOP;
	END;
$$ LANGUAGE plpgsql;
