-- Usage report in the TDX / AllSight format, queried like a view:
--
--   SELECT * FROM usage_report('2025-08-20', '2025-12-15');
--   SELECT * FROM usage_report('2025-08-20', '2025-12-15', ARRAY['ZWXTTCY5GW', 'ZM3296Y9XH']);
--
-- A plain view can't take a date range, so this is a function that returns a table.
-- Dates are inclusive and use the database's TimeZone setting for midnight.
-- Only completed sessions (st_sessions_history) count; a session still open isn't included yet.
-- Installed by init_db.py; safe to re-run.

CREATE OR REPLACE FUNCTION usage_report(
    p_start   date,
    p_end     date,
    p_devices text[] DEFAULT NULL  -- serials to include; NULL = every registered device
)
RETURNS TABLE (
    computers  bigint,  -- devices in scope
    peak       bigint,  -- most sessions open at the same moment
    total      bigint,  -- number of sessions
    total_time text,    -- summed session time, H:MM:SS (hours run past 24)
    date_range text,
    unused     bigint   -- devices in scope with no sessions in the range
)
LANGUAGE sql STABLE
AS $$
WITH sessions AS (
    -- Sessions overlapping the range, clipped to its edges.
    SELECT h.st_device_id,
           GREATEST(h.st_start_time, CAST(p_start AS timestamptz))   AS s_start,
           LEAST(h.st_end_time, CAST(p_end + 1 AS timestamptz))      AS s_end
    FROM st_sessions_history h
    WHERE h.st_start_time < CAST(p_end + 1 AS timestamptz)
      AND h.st_end_time   > CAST(p_start AS timestamptz)
      AND (p_devices IS NULL OR h.st_device_id = ANY (p_devices))
),
events AS (
    SELECT s_start AS t, 1 AS step FROM sessions
    UNION ALL
    SELECT s_end, -1 FROM sessions
),
open_counts AS (
    -- Ends sort before starts at the same instant, so back-to-back sessions aren't an overlap.
    SELECT SUM(step) OVER (ORDER BY t, step ROWS UNBOUNDED PRECEDING) AS open_now FROM events
),
totals AS (
    SELECT CASE WHEN p_devices IS NULL THEN (SELECT COUNT(*) FROM st_devices)
                ELSE cardinality(p_devices) END                                  AS computers,
           (SELECT COUNT(*) FROM sessions)                                       AS total,
           (SELECT COUNT(DISTINCT st_device_id) FROM sessions)                   AS used,
           (SELECT COALESCE(SUM(EXTRACT(EPOCH FROM s_end - s_start)), 0)::bigint
              FROM sessions)                                                     AS secs
)
SELECT computers,
       (SELECT COALESCE(MAX(open_now), 0) FROM open_counts),
       total,
       (secs / 3600) || ':' || lpad((mod(secs, 3600) / 60)::text, 2, '0')
                     || ':' || lpad(mod(secs, 60)::text, 2, '0'),
       to_char(p_start, 'FMMM/FMDD/YY') || ' - ' || to_char(p_end, 'FMMM/FMDD/YY'),
       GREATEST(computers - used, 0)
FROM totals;
$$;
