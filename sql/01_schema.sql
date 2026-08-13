-- ============================================================
-- 01_schema.sql 
-- ============================================================

DROP VIEW  IF EXISTS vw_monthly_summary;
DROP VIEW  IF EXISTS vw_daily_weather;
DROP TABLE IF EXISTS fact_daily_weather;
DROP TABLE IF EXISTS fact_weather_observations;
DROP TABLE IF EXISTS dim_element;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_station;

-- One row per physical weather station. Descriptive, slowly changing.
CREATE TABLE dim_station (
    station_id    VARCHAR(11) PRIMARY KEY,
    station_name  TEXT        NOT NULL,
    country_code  CHAR(2)     NOT NULL,
    country       TEXT        NOT NULL,
    latitude      NUMERIC(8,4) NOT NULL,
    longitude     NUMERIC(9,4) NOT NULL,
    elevation_m   NUMERIC(7,1),
    is_gsn        SMALLINT    NOT NULL DEFAULT 0,   -- GCOS Surface Network flagship
    wmo_id        VARCHAR(5),
    climate_zone  TEXT
);

-- One row per calendar date. Integer surrogate key YYYYMMDD.
CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,
    date          DATE    NOT NULL UNIQUE,
    year          SMALLINT NOT NULL,
    quarter       SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    month_name    CHAR(3)  NOT NULL,
    day           SMALLINT NOT NULL,
    day_of_week   SMALLINT NOT NULL,
    day_name      CHAR(3)  NOT NULL,
    day_of_year   SMALLINT NOT NULL,
    week_of_year  SMALLINT NOT NULL,
    is_weekend    SMALLINT NOT NULL,
    season_nh     VARCHAR(6) NOT NULL
);

-- One row per GHCN element (measurement type).
CREATE TABLE dim_element (
    element       CHAR(4) PRIMARY KEY,
    element_name  TEXT NOT NULL,
    unit          TEXT NOT NULL
);

-- BRONZE/AUDIT layer: NOAA's native grain, flags preserved.
CREATE TABLE fact_weather_observations (
    station_id  VARCHAR(11) NOT NULL REFERENCES dim_station(station_id),
    date_key    INTEGER     NOT NULL REFERENCES dim_date(date_key),
    element     CHAR(4)     NOT NULL REFERENCES dim_element(element),
    value       NUMERIC(8,1) NOT NULL,
    mflag       CHAR(1),     -- measurement method flag
    qflag       CHAR(1),     -- quality flag: NON-NULL means it FAILED NOAA QA
    sflag       CHAR(1),     -- data source flag
    PRIMARY KEY (station_id, date_key, element)
);

-- SILVER/CURATED layer: one row per station-day, QA failures excluded.
CREATE TABLE fact_daily_weather (
    station_id  VARCHAR(11) NOT NULL REFERENCES dim_station(station_id),
    date_key    INTEGER     NOT NULL REFERENCES dim_date(date_key),
    obs_date    DATE        NOT NULL,
    tmax NUMERIC(5,1), tmin NUMERIC(5,1), tavg NUMERIC(5,1), temp_range NUMERIC(5,1),
    prcp NUMERIC(7,1), snow NUMERIC(7,1), snwd NUMERIC(7,1),
    awnd NUMERIC(5,1), wsfg NUMERIC(5,1), wdfg NUMERIC(5,1), tsun NUMERIC(6,1),
    PRIMARY KEY (station_id, date_key)
);

-- Indexes mirror query patterns: filter by station, slice by time, filter by element.
CREATE INDEX idx_obs_station_date ON fact_weather_observations (station_id, date_key);
CREATE INDEX idx_obs_element      ON fact_weather_observations (element);
CREATE INDEX idx_daily_date       ON fact_daily_weather (date_key);
CREATE INDEX idx_daily_obsdate    ON fact_daily_weather (obs_date);
