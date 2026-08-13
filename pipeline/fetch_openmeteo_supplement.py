"""
fetch_openmeteo_supplement.py

Pulls the variables GHCN-Daily lacks (solar radiation, cloud cover, humidity,
dew point, pressure, wind gusts at hourly resolution) from the Open-Meteo
Historical Weather API, which serves ECMWF ERA5 reanalysis data.

These land in a supplementary fact table (Fact_ReanalysisDaily) so that raw
station observations and model reanalysis are never mixed silently. Being able
to explain THAT distinction is an interview differentiator.
"""
import requests
import pandas as pd

STATIONS = {
    "AU000005901": (48.2331, 16.3500),
    "CA003050520": (51.1833, -115.5667),
    "FMW00040308": (9.4833, 138.0833),
    "GM000010962": (47.8017, 11.0117),
    "ITE00100554": (45.4717, 9.1892),
    "MI000067693": (-15.6830, 34.9670),
    "RQW00011641": (18.4325, -66.0108),
    "USC00168923": (32.3994, -91.1842),
}

DAILY_VARS = ",".join([
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "dew_point_2m_mean", "relative_humidity_2m_mean", "surface_pressure_mean",
    "cloud_cover_mean", "shortwave_radiation_sum",
    "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant",
    "precipitation_sum", "rain_sum", "snowfall_sum",
    "sunrise", "sunset",
])

URL = ("https://archive-api.open-meteo.com/v1/archive"
       "?latitude={lat}&longitude={lon}"
       "&start_date=1990-01-01&end_date=2026-06-30"
       "&daily=" + DAILY_VARS + "&timezone=UTC")


def main():
    frames = []
    for sid, (lat, lon) in STATIONS.items():
        print(f"Fetching ERA5 daily series for {sid} ...")
        r = requests.get(URL.format(lat=lat, lon=lon), timeout=180)
        r.raise_for_status()
        d = r.json()["daily"]
        df = pd.DataFrame(d)
        df.insert(0, "station_id", sid)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out = out.rename(columns={"time": "obs_date"})
    out.to_csv("outputs/fact_reanalysis_daily.csv", index=False)
    print(f"Saved outputs/fact_reanalysis_daily.csv ({len(out):,} rows)")


if __name__ == "__main__":
    main()
