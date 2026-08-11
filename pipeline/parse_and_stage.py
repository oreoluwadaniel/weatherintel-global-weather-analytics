"""
parse_and_stage.py  (Milestone 2: ingestion)

Reads raw NOAA GHCN-Daily station files from raw/data/ and produces clean,
load-ready staging files in staging/.

Handles BOTH raw formats automatically:
  *.dly  : NOAA's fixed-width archive format (bundled with this project)
  *.csv  : NOAA's by_station CSV format (what refresh_ghcn_noaa.py downloads)

Run:  python pipeline/parse_and_stage.py
"""
import os
import calendar
import pandas as pd

RAW_DIR = "raw/data"
STAGE_DIR = "staging"

# The 10 elements our warehouse tracks (see Dim_Element)
ELEMENTS = {
    "TMAX": ("Maximum temperature", "deg C"), "TMIN": ("Minimum temperature", "deg C"),
    "TAVG": ("Average temperature", "deg C"), "PRCP": ("Precipitation", "mm"),
    "SNOW": ("Snowfall", "mm"), "SNWD": ("Snow depth", "mm"),
    "AWND": ("Average daily wind speed", "m/s"), "WSFG": ("Peak wind gust speed", "m/s"),
    "WDFG": ("Peak gust direction", "degrees"), "TSUN": ("Daily total sunshine", "minutes"),
}
TENTHS = {"TMAX", "TMIN", "TAVG", "PRCP", "AWND", "WSFG"}  # NOAA stores these x10

# Station metadata from NOAA ghcnd-stations.txt (embedded so no extra download)
STATIONS = [
    ("AU000005901", "Wien", "AU", "Austria", 48.2331, 16.3500, 199.0, 1, "11035", "Humid continental"),
    ("CA003050520", "Banff", "CA", "Canada", 51.1833, -115.5667, 1384.0, 0, "71122", "Subarctic mountain"),
    ("FMW00040308", "Yap Island Wso Ap", "FM", "Micronesia", 9.4833, 138.0833, 13.4, 1, "91490", "Tropical rainforest"),
    ("GM000010962", "Hohenpeissenberg", "GM", "Germany", 47.8017, 11.0117, 977.0, 1, "10962", "Temperate mountain"),
    ("ITE00100554", "Milan", "IT", "Italy", 45.4717, 9.1892, 150.0, 0, None, "Humid subtropical"),
    ("MI000067693", "Chileka", "MI", "Malawi", -15.6830, 34.9670, 767.0, 1, "67693", "Tropical savanna"),
    ("RQW00011641", "San Juan L M Marin Ap", "RQ", "Puerto Rico (US)", 18.4325, -66.0108, 2.7, 1, "78526", "Tropical monsoon"),
    ("USC00168923", "Tallulah", "US", "United States", 32.3994, -91.1842, 25.9, 0, None, "Humid subtropical"),
]


def parse_dly(path):
    """Parse NOAA fixed-width .dly archive format."""
    rec = []
    with open(path) as f:
        for line in f:
            element = line[17:21]
            if element not in ELEMENTS:
                continue
            year, month = int(line[11:15]), int(line[15:17])
            for day in range(1, calendar.monthrange(year, month)[1] + 1):
                o = 21 + (day - 1) * 8
                v = line[o:o + 5].strip()
                if v in ("", "-9999"):
                    continue
                rec.append((line[0:11], f"{year:04d}-{month:02d}-{day:02d}", element,
                            int(v), line[o+5].strip() or None,
                            line[o+6].strip() or None, line[o+7].strip() or None))
    return pd.DataFrame(rec, columns=["station_id", "obs_date", "element",
                                      "value_raw", "mflag", "qflag", "sflag"])


def parse_noaa_csv(path):
    """Parse NOAA AWS by_station CSV format (ID,DATE,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME)."""
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.upper().strip() for c in df.columns]
    df = df[df.ELEMENT.isin(ELEMENTS)]
    out = pd.DataFrame({
        "station_id": df.ID,
        "obs_date": pd.to_datetime(df.DATE, format="%Y%m%d").dt.strftime("%Y-%m-%d"),
        "element": df.ELEMENT,
        "value_raw": df.DATA_VALUE.astype(int),
        "mflag": df.M_FLAG.where(df.M_FLAG.notna() & (df.M_FLAG.str.strip() != ""), None),
        "qflag": df.Q_FLAG.where(df.Q_FLAG.notna() & (df.Q_FLAG.str.strip() != ""), None),
        "sflag": df.S_FLAG.where(df.S_FLAG.notna() & (df.S_FLAG.str.strip() != ""), None),
    })
    return out[out.value_raw != -9999]


def build_dim_date(start, end):
    d = pd.DataFrame({"dt": pd.date_range(start, end, freq="D")})
    return pd.DataFrame({
        "date_key": d.dt.dt.strftime("%Y%m%d").astype(int),
        "date": d.dt.dt.strftime("%Y-%m-%d"),
        "year": d.dt.dt.year, "quarter": d.dt.dt.quarter,
        "month": d.dt.dt.month, "month_name": d.dt.dt.strftime("%b"),
        "day": d.dt.dt.day, "day_of_week": d.dt.dt.dayofweek + 1,
        "day_name": d.dt.dt.strftime("%a"), "day_of_year": d.dt.dt.dayofyear,
        "week_of_year": d.dt.dt.isocalendar().week.astype(int),
        "is_weekend": (d.dt.dt.dayofweek >= 5).astype(int),
        "season_nh": d.dt.dt.month.map({12: "Winter", 1: "Winter", 2: "Winter",
                                        3: "Spring", 4: "Spring", 5: "Spring",
                                        6: "Summer", 7: "Summer", 8: "Summer",
                                        9: "Autumn", 10: "Autumn", 11: "Autumn"}),
    })


def main():
    os.makedirs(STAGE_DIR, exist_ok=True)
    frames = []
    for fn in sorted(os.listdir(RAW_DIR)):
        p = os.path.join(RAW_DIR, fn)
        if fn.endswith(".dly"):
            print(f"Parsing fixed-width {fn} ...")
            frames.append(parse_dly(p))
        elif fn.endswith(".csv") and fn[:-4] in [s[0] for s in STATIONS]:
            print(f"Parsing NOAA CSV {fn} ...")
            frames.append(parse_noaa_csv(p))
    long_df = pd.concat(frames, ignore_index=True)
    long_df = long_df.drop_duplicates(subset=["station_id", "obs_date", "element"])

    # Unit conversion happens HERE, once, in one documented place.
    long_df["value"] = long_df.apply(
        lambda r: r.value_raw / 10.0 if r.element in TENTHS else float(r.value_raw), axis=1)
    long_df["date_key"] = long_df.obs_date.str.replace("-", "").astype(int)

    # Curated wide daily fact: exclude values that failed NOAA quality assurance.
    curated = long_df[long_df.qflag.isna()]
    wide = curated.pivot_table(index=["station_id", "date_key", "obs_date"],
                               columns="element", values="value", aggfunc="first").reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={c: c.lower() for c in wide.columns})
    for col in ["tmax", "tmin", "tavg", "prcp", "snow", "snwd", "awnd", "wsfg", "wdfg", "tsun"]:
        if col not in wide.columns:
            wide[col] = None
    wide["temp_range"] = wide["tmax"] - wide["tmin"]

    # Write staging files
    pd.DataFrame(STATIONS, columns=["station_id", "station_name", "country_code", "country",
                                    "latitude", "longitude", "elevation_m", "is_gsn",
                                    "wmo_id", "climate_zone"]
                 ).to_csv(f"{STAGE_DIR}/dim_station.csv", index=False)
    build_dim_date(long_df.obs_date.min(), long_df.obs_date.max()
                   ).to_csv(f"{STAGE_DIR}/dim_date.csv", index=False)
    pd.DataFrame([{"element": k, "element_name": v[0], "unit": v[1]}
                  for k, v in ELEMENTS.items()]).to_csv(f"{STAGE_DIR}/dim_element.csv", index=False)
    long_df[["station_id", "date_key", "element", "value", "mflag", "qflag", "sflag"]
            ].to_csv(f"{STAGE_DIR}/fact_observations_long.csv", index=False)
    wide[["station_id", "date_key", "obs_date", "tmax", "tmin", "tavg", "temp_range",
          "prcp", "snow", "snwd", "awnd", "wsfg", "wdfg", "tsun"]
         ].to_csv(f"{STAGE_DIR}/fact_daily_weather.csv", index=False)

    print(f"\nStaged: {len(long_df):,} long observations, {len(wide):,} station-days")
    print(f"Date span: {long_df.obs_date.min()} to {long_df.obs_date.max()}")
    print(f"QA-flagged records excluded from curated layer: {long_df.qflag.notna().sum():,}")


if __name__ == "__main__":
    main()
