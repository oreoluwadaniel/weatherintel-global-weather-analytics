-- VIEW 1: The everything-joined daily view (the analyst's front door)
CREATE OR REPLACE VIEW vw_daily_weather AS
SELECT f.obs_date, d.year, d.month, d.month_name, d.season_nh,
       d.day_of_year, d.week_of_year,
       s.station_id, s.station_name, s.country, s.climate_zone,
       s.latitude, s.elevation_m,
       f.tmax, f.tmin, f.tavg, f.temp_range, f.prcp, f.snow, f.snwd,
       f.awnd, f.wsfg
FROM fact_daily_weather f
JOIN dim_station s USING (station_id)
JOIN dim_date d    USING (date_key);

-- VIEW 2: Monthly climate summary (feeds trend charts and Power BI)
CREATE OR REPLACE VIEW vw_monthly_summary AS
SELECT f.station_id, s.station_name, d.year, d.month, d.month_name,
       ROUND(AVG(f.tmax), 1) AS avg_tmax,
       ROUND(AVG(f.tmin), 1) AS avg_tmin,
       ROUND(SUM(f.prcp), 1) AS total_prcp,
       MAX(f.tmax)           AS hottest_day,
       MIN(f.tmin)           AS coldest_day,
       COUNT(f.tmax)         AS days_reported
FROM fact_daily_weather f
JOIN dim_station s USING (station_id)
JOIN dim_date d    USING (date_key)
GROUP BY f.station_id, s.station_name, d.year, d.month, d.month_name;

-- VIEW 3: Rolling averages. The frame clause "ROWS BETWEEN 6 PRECEDING AND
-- CURRENT ROW" means: this row plus the 6 before it, per station, in date
-- order. Rolling means smooth signal instead of daily noise, and these become
-- ML features in Milestone 7.
CREATE OR REPLACE VIEW vw_rolling_climate AS
SELECT station_id, obs_date, tmax, prcp,
       ROUND(AVG(tmax) OVER w7,  1) AS tmax_7d_avg,
       ROUND(AVG(tmax) OVER w30, 1) AS tmax_30d_avg,
       ROUND(SUM(prcp) OVER w30, 1) AS prcp_30d_total
FROM fact_daily_weather
WINDOW w7  AS (PARTITION BY station_id ORDER BY obs_date
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
       w30 AS (PARTITION BY station_id ORDER BY obs_date
               ROWS BETWEEN 29 PRECEDING AND CURRENT ROW);

-- VIEW 4: Record-breaking days. A day breaks the station's heat record when
-- its tmax exceeds the running maximum of all PRIOR days (frame ends at
-- 1 PRECEDING so today never competes with itself).
CREATE OR REPLACE VIEW vw_record_days AS
SELECT station_id, obs_date, tmax,
       MAX(tmax) OVER (PARTITION BY station_id ORDER BY obs_date
                       ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
           AS prior_record
FROM fact_daily_weather
WHERE tmax IS NOT NULL;

-- VIEW 5: Consecutive rainy-day streaks
CREATE OR REPLACE VIEW vw_rain_streaks AS
WITH rainy AS (
    SELECT station_id, obs_date,
           obs_date - (ROW_NUMBER() OVER (PARTITION BY station_id
                                          ORDER BY obs_date))::int AS streak_grp
    FROM fact_daily_weather
    WHERE prcp >= 1.0
)
SELECT station_id, MIN(obs_date) AS streak_start, MAX(obs_date) AS streak_end,
       COUNT(*) AS streak_days
FROM rainy
GROUP BY station_id, streak_grp;

-- VIEW 6: Extreme-event thresholds per station (95th/5th percentiles).
-- "Hot" is relative: 32 C is ordinary in San Juan and historic in Banff.
-- Insurance and energy clients price risk off these station-specific bands.
CREATE OR REPLACE VIEW vw_station_thresholds AS
SELECT station_id,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tmax) AS p95_tmax,
       PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY tmin) AS p05_tmin,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prcp)
           FILTER (WHERE prcp > 0)                        AS p95_wet_day_prcp
FROM fact_daily_weather
GROUP BY station_id;

-- ============================================================
-- EXPLORATION QUERIES: run each one, study the result
-- ============================================================

-- Q1: Ten most extreme record-breaking heat days in Vienna's 163-year record
SELECT obs_date, tmax, prior_record, ROUND(tmax - prior_record, 1) AS beat_by
FROM vw_record_days
WHERE station_id = 'AU000005901' AND tmax > prior_record
ORDER BY beat_by DESC
LIMIT 10;

-- Q2: Longest rain streak per station, with names
SELECT s.station_name, r.streak_start, r.streak_end, r.streak_days
FROM vw_rain_streaks r
JOIN dim_station s USING (station_id)
WHERE (r.station_id, r.streak_days) IN (
    SELECT station_id, MAX(streak_days) FROM vw_rain_streaks GROUP BY station_id)
ORDER BY r.streak_days DESC;

-- Q3: Is Vienna warming? Decade averages with change vs previous decade (LAG)
WITH by_decade AS (
    SELECT (d.year / 10) * 10 AS decade, ROUND(AVG(f.tavg), 2) AS avg_temp
    FROM fact_daily_weather f JOIN dim_date d USING (date_key)
    WHERE f.station_id = 'AU000005901' AND f.tavg IS NOT NULL
    GROUP BY (d.year / 10) * 10
)
SELECT decade, avg_temp,
       ROUND(avg_temp - LAG(avg_temp) OVER (ORDER BY decade), 2) AS change_vs_prev
FROM by_decade
ORDER BY decade;

-- Q4: Days per year exceeding each station's own 95th percentile heat
-- threshold (the heatwave-frequency trend insurers care about)
SELECT d.year, s.station_name, COUNT(*) AS extreme_heat_days
FROM fact_daily_weather f
JOIN dim_date d USING (date_key)
JOIN dim_station s USING (station_id)
JOIN vw_station_thresholds t ON t.station_id = f.station_id
WHERE f.tmax > t.p95_tmax AND d.year >= 1990
GROUP BY d.year, s.station_name
ORDER BY s.station_name, d.year;
