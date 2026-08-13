"""
Builds the supervised learning dataset for our prediction target:
    TOMORROW'S maximum temperature in Vienna.

The golden rule enforced throughout: every feature must be computable at
prediction time. When forecasting tomorrow, we may use today and the past,
never tomorrow. Violating this is called leakage and it is the number one
way portfolio ML projects embarrass their authors in interviews.

Output: outputs/model_dataset_vienna.csv
"""
import os
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:postgres@localhost:5432/weatherintel"

eng = create_engine(DB_URL)
v = pd.read_sql("""
    SELECT obs_date, tmax, tmin, tavg, temp_range, prcp
    FROM fact_daily_weather
    WHERE station_id = 'AU000005901' AND obs_date >= '1960-01-01'
    ORDER BY obs_date
""", eng, parse_dates=["obs_date"]).set_index("obs_date")
print(f"Vienna raw: {len(v):,} days, {v.index.min().date()} to {v.index.max().date()}")

v = v.reindex(pd.date_range(v.index.min(), v.index.max(), freq="D"))
print(f"After calendar reindex: {len(v):,} rows ({v.tmax.isna().sum()} missing days now explicit)")

f = pd.DataFrame(index=v.index)

# --- TARGET: tomorrow's tmax (shift -1 pulls the future back one row) ------
f["target_tmax_next_day"] = v.tmax.shift(-1)

# --- LAG FEATURES: recent thermal memory ------------------------------------
# Weather is autocorrelated: today's airmass is usually still there tomorrow.
# Lag 1 is the single strongest predictor at a 1-day horizon.
for lag in (1, 2, 3, 7):
    f[f"tmax_lag{lag}"] = v.tmax.shift(lag - 1)   # lag1 = today, lag2 = yesterday...
f["tmin_today"] = v.tmin
f["temp_range_today"] = v.temp_range              # clear vs cloudy proxy

# --- ROLLING FEATURES: smoothed regime signal --------------------------------
# 7-day mean captures the current weather regime; 30-day captures the season
# as actually experienced this year (a warm March vs the average March).
f["tmax_roll7_mean"] = v.tmax.rolling(7, min_periods=5).mean()
f["tmax_roll30_mean"] = v.tmax.rolling(30, min_periods=20).mean()
f["tmax_roll7_std"] = v.tmax.rolling(7, min_periods=5).std()   # volatility: frontal activity

# --- TREND FEATURE: is the air warming or cooling right now? -----------------
f["tmax_delta_1d"] = v.tmax - v.tmax.shift(1)

# --- PRECIPITATION MEMORY ----------------------------------------------------
# Wet ground cools the following days (evaporative cooling); rain also flags
# cloud regimes that suppress daytime highs.
f["prcp_today"] = v.prcp.fillna(0)
f["prcp_roll7_sum"] = v.prcp.fillna(0).rolling(7, min_periods=5).sum()

# --- SEASONAL ENCODING: sine/cosine, not raw day-of-year --------------------
# Raw day-of-year tells a model Dec 31 (365) and Jan 1 (1) are maximally far
# apart. The sine/cosine pair places every day on a circle, so winter days
# sit next to each other as physics demands.
doy = f.index.dayofyear
f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
f["month"] = f.index.month

# --- FINALIZE ----------------------------------------------------------------
before = len(f)
f = f.dropna()
print(f"Dropped {before - len(f):,} rows with incomplete features/target "
      f"(gaps + warm-up windows + final day)")
print(f"Model dataset: {len(f):,} rows x {f.shape[1] - 1} features")

os.makedirs("outputs", exist_ok=True)
f.to_csv("outputs/model_dataset_vienna.csv", index_label="obs_date")
print("Saved outputs/model_dataset_vienna.csv")
print("\nFeature preview:")
print(f.tail(3).round(2).to_string())
