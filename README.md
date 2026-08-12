# WeatherIntel: Weather Analytics & Forecast Evaluation

**A weather intelligence pipeline that turns raw NOAA observations into trusted historical analysis, forecast benchmarks, and decision-ready reporting.**

**Source:** NOAA GHCN-Daily  
**Stations:** 8 across 4 continents  
**Curated observations:** 371,482 station-days  
**History:** 1763 to March 2018, depending on station  
**Stack:** Python, PostgreSQL, SQL, XGBoost, SARIMA, Power BI

---

## The business problem

Weather data is useful only when the underlying observations can be trusted.

For industries such as agriculture, logistics, aviation, insurance, and renewable energy, poor coverage, missing observations, inconsistent quality, and weak forecasts can lead to bad operational decisions.

WeatherIntel builds the layer between raw weather archives and those decisions.

It takes NOAA station records, preserves the original quality information, removes observations that fail defined quality checks, stores the result in a PostgreSQL warehouse, evaluates forecasting models against simple baselines, and exposes the results through Power BI.

---

## How it works

```text
NOAA Weather Records
        ↓
Parse & Standardize
        ↓
Quality Checks
        ↓
PostgreSQL Star Schema
        ↓
Historical Analysis + Forecasting
        ↓
Power BI
        ↓
Operational Decisions
