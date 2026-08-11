"""
10_xgboost.py  (Milestone 10: Gradient Boosting + Final Evaluation)

XGBoost on the Milestone 7 feature set, evaluated on the SAME chronological
split as the baselines so the comparison is fair. Then the final scoreboard.

Why XGBoost here: it learns interactions and non-linearities automatically
(e.g. "a big temp_range in June means clear skies means hot tomorrow, but
the same range in January means something different"). Linear regression
cannot express that without hand-built interaction terms.

Run: python pipeline/10_xgboost.py   (after 07 and 08)
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

df = pd.read_csv("outputs/model_dataset_vienna.csv",
                 parse_dates=["obs_date"]).set_index("obs_date")
SPLIT = "2010-01-01"
train, test = df[df.index < SPLIT], df[df.index >= SPLIT]
y_tr, y_te = train.target_tmax_next_day, test.target_tmax_next_day
X_tr = train.drop(columns="target_tmax_next_day")
X_te = test.drop(columns="target_tmax_next_day")

# Conservative hyperparameters. Weather has irreducible noise; a deep,
# unregularized tree ensemble will happily memorize that noise.
#   max_depth 4       : shallow trees generalize
#   learning_rate 0.05 + 600 trees : many small careful steps
#   subsample/colsample 0.8        : each tree sees a different world (variance down)
model = XGBRegressor(n_estimators=600, max_depth=4, learning_rate=0.05,
                     subsample=0.8, colsample_bytree=0.8,
                     objective="reg:squarederror", random_state=42)
model.fit(X_tr, y_tr)
pred = model.predict(X_te)

mae = mean_absolute_error(y_te, pred)
rmse = root_mean_squared_error(y_te, pred)
print(f"XGBoost               MAE {mae:5.2f}  RMSE {rmse:5.2f}  (deg C)")

scores = pd.read_csv("outputs/model_scores.csv", index_col=0)
scores.loc["XGBoost"] = [mae, rmse]
scores = scores.sort_values("MAE", ascending=False)
scores.to_csv("outputs/model_scores.csv")
print("\nFINAL SCOREBOARD (Vienna, next-day TMAX, test 2010-2018):")
print(scores.round(2).to_string())

skill = (1 - scores.loc["XGBoost", "MAE"] / scores.loc["Persistence", "MAE"]) * 100
print(f"\nSkill vs persistence: {skill:.1f}% MAE reduction. Real weather models "
      "fight for single-digit percentage gains; do not expect miracles.")

# Feature importance: gain-based, i.e. how much each feature improved splits.
imp = pd.Series(model.feature_importances_, index=X_tr.columns).sort_values()
fig, ax = plt.subplots(figsize=(8, 6))
imp.plot.barh(ax=ax)
ax.set_title("XGBoost Feature Importance (gain), Next-Day TMAX Vienna")
plt.tight_layout(); plt.savefig("outputs/fig7_feature_importance.png", dpi=130)

# Scoreboard chart for the README / dashboard
fig, ax = plt.subplots(figsize=(8, 4.5))
scores.MAE.plot.barh(ax=ax, color=["#c0c0c0"] * (len(scores) - 1) + ["#2a7"])
ax.set(title="Next-Day TMAX Forecast Error by Model (lower is better)",
       xlabel="MAE (deg C)")
plt.tight_layout(); plt.savefig("outputs/fig8_model_comparison.png", dpi=130)

# Error diagnostics by month: WHEN does the model fail? Spring and autumn
# transitions are where 1-day forecasts hurt; executives ask exactly this.
err = pd.DataFrame({"month": y_te.index.month, "abs_err": (y_te - pred).abs()})
monthly_err = err.groupby("month").abs_err.mean()
print("\nMean absolute error by month (find the hard seasons):")
print(monthly_err.round(2).to_string())

pd.DataFrame({"obs_date": y_te.index, "actual": y_te.values,
              "predicted": pred}).to_csv("outputs/predictions_vienna.csv", index=False)
print("\nSaved predictions_vienna.csv, fig7, fig8. Milestone 10 complete.")
