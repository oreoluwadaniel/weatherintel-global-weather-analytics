"""
Model Vienna's MONTHLY mean tmax, not daily values. Daily SARIMA with a
365-day season is computationally miserable and statistically fragile;
monthly with a 12-period season is the professional norm for climate-scale
questions. Choosing the right grain for the question IS the senior skill.

SARIMA(p,d,q)(P,D,Q,s) in plain words:
  (1,0,1)    : this month relates to last month plus a moving-average error
  (1,1,1,12) : seasonal difference (subtract same month last year) removes
               the annual cycle, then model what remains
"""
import warnings
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_error

warnings.filterwarnings("ignore")

DB_URL = "postgresql://postgres:postgres@localhost:5432/weatherintel"

eng = create_engine(DB_URL)
m = pd.read_sql("""
    SELECT year, month, avg_tmax
    FROM vw_monthly_summary
    WHERE station_id = 'AU000005901' AND year BETWEEN 1960 AND 2017
      AND days_reported >= 20     -- a monthly mean from 3 days is not a mean
    ORDER BY year, month
""", eng)
m["date"] = pd.to_datetime(m.year.astype(str) + "-" + m.month.astype(str) + "-01")
ts = m.set_index("date").avg_tmax.asfreq("MS").interpolate(limit=2)
print(f"Monthly series: {len(ts)} months, {ts.index.min():%Y-%m} to {ts.index.max():%Y-%m}")

# Chronological holdout: final 24 months
train, test = ts[:-24], ts[-24:]

model = SARIMAX(train, order=(1, 0, 1), seasonal_order=(1, 1, 1, 12),
                enforce_stationarity=False, enforce_invertibility=False)
fit = model.fit(disp=False)
print(fit.summary().tables[1])

fc = fit.get_forecast(steps=24)
pred = fc.predicted_mean
ci = fc.conf_int()

mae = mean_absolute_error(test, pred)
seasonal_naive = ts.shift(12)[-24:]              # same month last year
naive_mae = mean_absolute_error(test, seasonal_naive)
print(f"\nSARIMA 24-month forecast MAE : {mae:.2f} deg C")
print(f"Seasonal-naive baseline MAE  : {naive_mae:.2f} deg C")
print("SARIMA must beat seasonal-naive to justify its existence."
      if mae < naive_mae else "Seasonal-naive won: say so honestly, it happens.")

fig, ax = plt.subplots(figsize=(11, 5))
ts[-72:].plot(ax=ax, label="Observed", linewidth=1.2)
pred.plot(ax=ax, label="SARIMA forecast", linewidth=2)
ax.fill_between(ci.index, ci.iloc[:, 0], ci.iloc[:, 1], alpha=0.2,
                label="95% interval")
ax.set(title="Vienna Monthly Mean TMAX: SARIMA 24-Month Holdout",
       ylabel="deg C"); ax.legend()
plt.tight_layout(); plt.savefig("outputs/fig6_sarima_vienna.png", dpi=130)
print("Saved outputs/fig6_sarima_vienna.png")

# The interval is the product. Airlines and insurers do not buy a line,
# they buy the band: "monthly mean will fall between X and Y with 95%
# confidence" is a priceable statement.
