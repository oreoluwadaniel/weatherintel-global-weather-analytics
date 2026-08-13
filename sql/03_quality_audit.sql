-- AUDIT 1: What did NOAA's own quality assurance reject, and why?
-- qflag meanings: I=internal consistency fail, X=bounds fail, O=climatological
-- outlier, S=spatial inconsistency, N=naught check, G=gap check, D=duplicate check
SELECT qflag, COUNT(*) AS failed_records
FROM fact_weather_observations
WHERE qflag IS NOT NULL
GROUP BY qflag
ORDER BY failed_records DESC;

-- AUDIT 2: Physical impossibility check: days where TMIN > TMAX.
-- These should be ZERO in the curated table (we excluded QA failures).
-- If any survive, NOAA's checks missed them and ours caught them.
SELECT s.station_name, f.obs_date, f.tmax, f.tmin
FROM fact_daily_weather f
JOIN dim_station s USING (station_id)
WHERE f.tmin > f.tmax
ORDER BY f.obs_date;

-- AUDIT 3: Completeness per station per decade (the coverage map).
-- This is the query that exposes Chileka and Banff.
SELECT s.station_name,
       (d.year / 10) * 10 AS decade,
       COUNT(f.tmax) AS days_with_tmax,
       ROUND(COUNT(f.tmax) * 100.0 / (365.25 * 10), 1) AS pct_complete
FROM fact_daily_weather f
JOIN dim_station s USING (station_id)
JOIN dim_date d USING (date_key)
GROUP BY s.station_name, (d.year / 10) * 10
ORDER BY s.station_name, decade;

-- AUDIT 4: Gap analysis with window functions.
-- LAG() looks at the previous row within each station's date-ordered history;
-- the difference between consecutive observation dates reveals every hole.
WITH gaps AS (
    SELECT station_id, obs_date,
           obs_date - LAG(obs_date) OVER (PARTITION BY station_id
                                          ORDER BY obs_date) AS days_since_prev
    FROM fact_daily_weather
)
SELECT s.station_name,
       COUNT(*) FILTER (WHERE days_since_prev > 1)  AS gap_count,
       MAX(days_since_prev)                          AS longest_gap_days
FROM gaps g
JOIN dim_station s USING (station_id)
GROUP BY s.station_name
ORDER BY longest_gap_days DESC;

-- AUDIT 5: Outlier scan: values beyond plausible physical bounds per element.
-- World records: highest air temp 56.7 C, lowest -89.2 C, max daily rain ~1825 mm.
SELECT s.station_name, f.obs_date, 'tmax' AS metric, f.tmax AS value
FROM fact_daily_weather f JOIN dim_station s USING (station_id)
WHERE f.tmax > 50 OR f.tmax < -60
UNION ALL
SELECT s.station_name, f.obs_date, 'prcp', f.prcp
FROM fact_daily_weather f JOIN dim_station s USING (station_id)
WHERE f.prcp > 500
ORDER BY value DESC;

-- AUDIT 6: Duplicate grain check. The PK makes duplicates impossible,
-- but a senior verifies the constraint did its job. Expect zero rows.
SELECT station_id, date_key, COUNT(*)
FROM fact_daily_weather
GROUP BY station_id, date_key
HAVING COUNT(*) > 1;

-- ============================================================
-- THE CLEANING DECISION (run after reading all audits above)
-- We do NOT delete or interpolate in the warehouse. We define a
-- model-ready view: recent, dense, active stations only.
-- Interpolation, if any, happens later in Python where it can be
-- documented per model. Never silently fill weather data: a
-- forward-filled rainstorm is a lie.
-- ============================================================
CREATE OR REPLACE VIEW vw_model_ready AS
SELECT f.*
FROM fact_daily_weather f
WHERE f.obs_date >= DATE '1960-01-01'
  AND f.station_id IN (
      -- keep stations with at least 95% TMAX coverage since 1990
      SELECT station_id
      FROM fact_daily_weather
      WHERE obs_date >= DATE '1990-01-01'
      GROUP BY station_id
      HAVING COUNT(tmax) >= 0.95 * (DATE '2018-03-01' - DATE '1990-01-01')
  );

-- Verify which stations qualified:
SELECT DISTINCT s.station_name
FROM vw_model_ready v JOIN dim_station s USING (station_id);
