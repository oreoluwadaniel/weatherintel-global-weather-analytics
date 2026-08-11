"""
08_baseline.py  (Milestone 8: Baselines)

Trains the models every serious forecast must beat BEFORE any fancy ML:
  1. Persistence : tomorrow = today            (the meteorologist's null model)
  2. Climatology : tomorrow = day-of-year mean (the "average year" model)
  3. Linear Regression on our engineered features

Split is CHRONOLOGICAL: train on 1960-2009, test on 2010-2018. Never shuffle
time series. Shuffling lets the model peek at the future's neighbours and
produces glorious fake accuracy that dies in production.

Run: python pipeline/08_baseline.py   (after 07_features.py)
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

df = pd.read_csv("outputs/model_dataset_vienna.csv",
                 parse_dates=["obs_date"]).set_index("obs_date")

SPLIT = "2010-01-01"
train, test = df[df.index < SPLIT], df[df.index >= SPLIT]
y_tr, y_te = train.target_tmax_next_day, test.target_tmax_next_day
X_tr = train.drop(columns="target_tmax_next_day")
X_te = test.drop(columns="target_tmax_next_day")
print(f"Train: {len(train):,} rows (to 2009)   Test: {len(test):,} rows (2010+)")

results = {}

def score(name, pred):
    mae = mean_absolute_error(y_te, pred)
    rmse = root_mean_squared_error(y_te, pred)
    results[name] = (mae, rmse)
    print(f"{name:22s} MAE {mae:5.2f}  RMSE {rmse:5.2f}  (deg C)")

# 1. Persistence: our tmax_lag1 feature IS today's tmax, so it IS the forecast
score("Persistence", X_te.tmax_lag1)

# 2. Climatology: mean target per day-of-year, learned on TRAIN only
# (computing it on all data would leak test information into the baseline)
clim = y_tr.groupby(train.index.dayofyear).mean()
score("Climatology", test.index.dayofyear.map(clim).values)

# 3. Linear Regression on the engineered features
lr = LinearRegression().fit(X_tr, y_tr)
score("Linear Regression", lr.predict(X_te))

# Which features did the linear model lean on? Coefficients are interpretable
# because features share units or are bounded; still, treat signs with care
# when predictors are correlated (tmax_lag1 vs roll7 mean).
coefs = pd.Series(lr.coef_, index=X_tr.columns).sort_values(key=abs, ascending=False)
print("\nTop linear coefficients:")
print(coefs.head(6).round(3).to_string())

pd.DataFrame(results, index=["MAE", "RMSE"]).T.to_csv("outputs/model_scores.csv")
print("\nScores appended to outputs/model_scores.csv")
print("\nRead this table like a senior: Persistence is the bar. Any model that "
      "cannot beat 'tomorrow equals today' has learned nothing about weather.")
