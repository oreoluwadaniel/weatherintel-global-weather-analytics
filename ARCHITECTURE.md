# Data Architecture

```text
NOAA source files
      |
      v
Python ingestion
      |
      +--> schema checks
      +--> unit handling
      +--> missing-value checks
      +--> quality flags
      |
      v
PostgreSQL
      |
      +--> station dimensions
      +--> date dimensions
      +--> weather facts
      +--> audit observations
      |
      v
SQL analytical layer
      |
      +--> station trends
      +--> climate summaries
      +--> quality reporting
      |
      v
Power BI
      |
      +--> monitoring
      +--> comparisons
      +--> forecast results
      |
      v
Model evaluation
      |
      +--> baseline
      +--> SARIMA
      +--> XGBoost
```

## Quality rule

Failed observations are not simply removed. They are flagged and retained in the audit layer so the final analytical population can be traced back to the source.

## Forecast rule

Candidate models are compared with baselines. A model is not treated as useful merely because it produces a forecast.
