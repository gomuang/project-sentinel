-- Checks usage_report() with made-up sessions. Everything runs in its own schema
-- inside one transaction and is rolled back, so it's safe against a real database:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/test_usage_report.sql

BEGIN;
CREATE SCHEMA usage_report_test;
SET LOCAL search_path = usage_report_test;
SET LOCAL TimeZone = 'UTC';

CREATE TABLE st_devices (st_device_id text PRIMARY KEY);
CREATE TABLE st_sessions_history (
    st_device_id  text,
    st_start_time timestamptz,
    st_end_time   timestamptz
);
\ir ../usage_report.sql

INSERT INTO st_devices VALUES ('A'), ('B'), ('C');  -- C never used in September
INSERT INTO st_sessions_history VALUES
    ('A', '2025-09-01 09:00', '2025-09-01 10:00'),  -- 1h
    ('B', '2025-09-01 09:30', '2025-09-01 11:00'),  -- 1.5h, overlaps A -> peak 2
    ('A', '2025-09-02 09:00', '2025-09-02 09:30'),  -- 0.5h
    ('A', '2025-09-02 10:00', '2025-09-02 11:00'),  -- 1h, back to back with the next
    ('B', '2025-09-02 11:00', '2025-09-02 12:00'),  -- 1h, not an overlap
    ('B', '2025-08-31 22:00', '2025-09-01 01:00'),  -- starts before range: 1h inside
    ('B', '2025-09-02 23:00', '2025-09-03 02:00'),  -- ends after range: 1h inside
    ('A', '2025-09-03 05:00', '2025-09-03 06:00'),  -- after range: excluded
    ('C', '2025-11-01 00:00', '2025-11-02 06:15:15'); -- 30h15m15s, for H:MM:SS past 24h

DO $$
DECLARE r record;
BEGIN
    SELECT * INTO r FROM usage_report('2025-09-01', '2025-09-02');
    ASSERT (r.computers, r.peak, r.total, r.total_time, r.date_range, r.unused)
         = (3::bigint, 2::bigint, 7::bigint, '7:00:00', '9/1/25 - 9/2/25', 1::bigint),
           format('all devices: %s', r);

    SELECT * INTO r FROM usage_report('2025-09-01', '2025-09-02', ARRAY['A', 'C']);
    ASSERT (r.computers, r.peak, r.total, r.total_time, r.unused)
         = (2::bigint, 1::bigint, 3::bigint, '2:30:00', 1::bigint),
           format('device filter: %s', r);

    SELECT * INTO r FROM usage_report('2025-10-01', '2025-10-01');
    ASSERT (r.computers, r.peak, r.total, r.total_time, r.unused)
         = (3::bigint, 0::bigint, 0::bigint, '0:00:00', 3::bigint),
           format('empty range: %s', r);

    SELECT * INTO r FROM usage_report('2025-11-01', '2025-11-02', ARRAY['C']);
    ASSERT r.total_time = '30:15:15', format('hours past 24: %s', r);
END
$$;

\echo usage_report tests OK
ROLLBACK;
