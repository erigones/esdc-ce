-- See: 
-- https://support.zabbix.com/browse/ZBX-11257
-- https://www.keithf4.com/table-partitioning-and-foreign-keys/

--
-- Repair foreign key constraint c_event_recovery_1 on event_recovery
--
ALTER TABLE event_recovery DROP CONSTRAINT c_event_recovery_1;
CREATE OR REPLACE FUNCTION event_recovery_1_fk_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
v_event_id    bigint;
BEGIN
    -- check for event id
    SELECT eventid INTO v_event_id
    FROM events e
    WHERE e.eventid = NEW.eventid;

    IF v_event_id IS NULL THEN
        RAISE foreign_key_violation USING 
            MESSAGE='Insert or update on table "event_recovery" violates custom foreign key trigger "event_recovery_fk_trigger" ',
            DETAIL='Key (eventid=' || NEW.eventid || ') is not present in events table';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER event_recovery_1_fk_trigger 
	BEFORE INSERT OR UPDATE OF eventid ON event_recovery
	FOR EACH ROW
	EXECUTE PROCEDURE event_recovery_1_fk_trigger();

--
-- Repair foreign key constraint c_event_recovery_2 on event_recovery
--
ALTER TABLE event_recovery DROP CONSTRAINT c_event_recovery_2;
CREATE OR REPLACE FUNCTION event_recovery_2_fk_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
v_event_id    bigint;
BEGIN
    -- check for recovery event id
    SELECT eventid INTO v_event_id
    FROM events e
    WHERE e.eventid = NEW.r_eventid;

    IF v_event_id IS NULL THEN
        RAISE foreign_key_violation USING 
            MESSAGE='Insert or update on table "event_recovery" violates custom foreign key trigger "event_recovery_fk_trigger" ',
            DETAIL='Key (eventid=' || NEW.r_eventid || ') is not present in events table';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER event_recovery_2_fk_trigger 
	BEFORE INSERT OR UPDATE OF r_eventid ON event_recovery
	FOR EACH ROW
	EXECUTE PROCEDURE event_recovery_2_fk_trigger();

--
-- Repair foreign key constraint on problem
--
ALTER TABLE problem DROP CONSTRAINT c_problem_1;
CREATE OR REPLACE FUNCTION problem_1_fk_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
v_event_id    bigint;
BEGIN
    -- check for event id
    SELECT eventid INTO v_event_id
    FROM events e
    WHERE e.eventid = NEW.eventid;

    IF v_event_id IS NULL THEN
        RAISE foreign_key_violation USING 
            MESSAGE='Insert or update on table "problem" violates custom foreign key trigger "problem_fk_trigger" ',
            DETAIL='Key (eventid=' || NEW.eventid || ') is not present in events table';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER problem_1_fk_trigger 
	BEFORE INSERT OR UPDATE OF eventid ON problem
	FOR EACH ROW
	EXECUTE PROCEDURE problem_1_fk_trigger();

