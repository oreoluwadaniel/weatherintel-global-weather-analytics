"""
06_eda.py  (Milestone 6: Exploratory Data Analysis)

Pulls curated data from PostgreSQL and produces the five core EDA artefacts
every forecasting project needs BEFORE any model is trained:
  1. Seasonality   : monthly climatology per station
  2. Trend         : Vienna annual mean temperature with 10-year rolling mean
  3. Missingness   : yearly observation counts per station
  4. Anomalies     : days deviating > 3 sigma from their day-of-year normal
  5. Correlations  : variable relationships at the model station (Vienna)

All charts are saved to outputs/ as PNG. Run: python pipeline/06_eda.py
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# >>> EDIT with your credentials <<<
DB_URL = "postgresql://postgres:postgres@localhost:5432/weatherintel"

os.makedirs("outputs", exist_ok=True)
eng = create_engine(DB_URL)

df = pd.read_sql("""
    SELECT f.obs_date, f.station_id, s.station_name,
           f.tmax, f.tmin, f.tavg, f.temp_range, f.prcp, f.snow
    FROM fact_daily_weather f
    JOIN dim_station s USING (station_id)
""", eng, parse_dates=["obs_date"])
print(f"Loaded {len(df):,} station-days from Postgres")

# ---- 1. SEASONALITY: monthly climatology ---------------------------------
# Why: every forecasting model must beat the seasonal cycle to be useful.
# Averaging tmax by calendar month reveals each station's cycle shape.
clim = (df.assign(month=df.obs_date.dt.month)
          .groupby(["station_name", "month"]).tmax.mean().unstack(0))
ax = clim.plot(figsize=(11, 6), marker="o", linewidth=1.5)
ax.set(title="Monthly Climatology: Average Daily Max Temperature",
       xlabel="Month", ylabel="Avg TMAX (deg C)")
ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig("outputs/fig1_seasonality.png", dpi=130); plt.close()
flat = clim.max() - clim.min()
print("\nSeasonal amplitude (hottest minus coldest month, deg C):")
print(flat.sort_values(ascending=False).round(1).to_string())

# ---- 2. TREND: Vienna annual mean + 10y rolling ---------------------------
# Why: a trend violates the stationarity assumption of classical models
# (ARIMA) and must be known before choosing differencing terms.
v = df[df.station_id == "AU000005901"].set_index("obs_date")
annual = v.tavg.resample("YE").mean().dropna()
annual = annual[annual.index.year < 2018]           # drop partial final year
ax = annual.plot(figsize=(11, 5), alpha=0.45, label="Annual mean")
annual.rolling(10).mean().plot(ax=ax, linewidth=2.5, label="10-year rolling")
ax.set(title="Vienna Annual Mean Temperature 1855-2017",
       ylabel="deg C"); ax.legend()
plt.tight_layout(); plt.savefig("outputs/fig2_trend_vienna.png", dpi=130); plt.close()
warming = annual.tail(30).mean() - annual.head(30).mean()
print(f"\nVienna: last 30 years vs first 30 years: +{warming:.2f} deg C")

# ---- 3. MISSINGNESS: yearly coverage per station --------------------------
# Why: models trained across invisible gaps learn false transitions.
cov = (df.assign(year=df.obs_date.dt.year)
         .groupby(["station_name", "year"]).tmax.count().unstack(0))
ax = cov.plot(figsize=(11, 6), linewidth=1.2)
ax.axhline(365, color="grey", linestyle="--", linewidth=0.8)
ax.set(title="Observations per Year per Station (365 = complete)",
       ylabel="Days with TMAX"); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig("outputs/fig3_missingness.png", dpi=130); plt.close()

# ---- 4. ANOMALIES: 3-sigma departures from day-of-year normals ------------
# Why: meteorology defines anomaly as departure from the day-of-year normal,
# never from the overall mean (a 20C January day in Vienna is the anomaly,
# a 20C May day is not). This is also exactly how QA teams flag suspects.
v = v.reset_index()
v["doy"] = v.obs_date.dt.dayofyear
norm = v.groupby("doy").tmax.agg(["mean", "std"]).rename(
    columns={"mean": "doy_mean", "std": "doy_std"})
v = v.join(norm, on="doy")
v["z"] = (v.tmax - v.doy_mean) / v.doy_std
anoms = v[v.z.abs() > 3]
print(f"\nVienna days beyond 3 sigma of their day-of-year normal: {len(anoms)}")
print(anoms.nlargest(5, "z")[["obs_date", "tmax", "doy_mean", "z"]].round(2).to_string(index=False))
fig, ax = plt.subplots(figsize=(11, 5))
recent = v[v.obs_date.dt.year >= 2000]
ax.plot(recent.obs_date, recent.tmax, linewidth=0.4, alpha=0.6)
ra = recent[recent.z.abs() > 3]
ax.scatter(ra.obs_date, ra.tmax, color="red", s=18, zorder=3,
           label=f"> 3 sigma anomaly (n={len(ra)})")
ax.set(title="Vienna Daily TMAX 2000-2018 with Statistical Anomalies",
       ylabel="deg C"); ax.legend()
plt.tight_layout(); plt.savefig("outputs/fig4_anomalies_vienna.png", dpi=130); plt.close()

# ---- 5. CORRELATIONS at the model station ---------------------------------
# Why: tells us which variables carry predictive signal for TMAX, and warns
# about multicollinearity (tavg vs tmax) before linear modeling.
corr = v[["tmax", "tmin", "tavg", "temp_range", "prcp"]].corr()  # snow: not reported at Vienna
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=45)
ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.columns)
for i in range(len(corr)):
    for j in range(len(corr)):
        ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=9)
ax.set_title("Variable Correlations, Vienna")
plt.colorbar(im); plt.tight_layout()
plt.savefig("outputs/fig5_correlation_vienna.png", dpi=130); plt.close()
print("\nCorrelation of each variable with TMAX (Vienna):")
print(corr.tmax.drop("tmax").round(2).to_string())
print("\nEDA complete. Five figures written to outputs/")
