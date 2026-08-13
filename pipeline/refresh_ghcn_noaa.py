import os
import requests

STATIONS = [
    "AU000005901",  # Vienna, Austria           (1855 -> present)
    "CA003050520",  # Banff, Canada             (1887 -> present)
    "FMW00040308",  # Yap Island Airport, FM    (1951 -> present)
    "GM000010962",  # Hohenpeissenberg, Germany (1781 -> present)
    "ITE00100554",  # Milan, Italy              (1763 -> 2008)
    "MI000067693",  # Chileka, Malawi           (1939 -> present)
    "RQW00011641",  # San Juan LMM Airport, PR  (1956 -> present)
    "USC00168923",  # Tallulah, Louisiana, US   (1907 -> present)
]

BASE = "https://noaa-ghcn-pds.s3.amazonaws.com/csv/by_station/{sid}.csv"
OUT = "raw/data"


def main():
    os.makedirs(OUT, exist_ok=True)
    for sid in STATIONS:
        url = BASE.format(sid=sid)
        print(f"Downloading {sid} from NOAA ...")
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(f"{OUT}/{sid}.csv", "wb") as f:
            f.write(r.content)
        print(f"  saved {len(r.content)/1e6:.1f} MB")
    print("Done. The by_station CSVs use columns: ID, DATE, ELEMENT, DATA_VALUE, "
          "M_FLAG, Q_FLAG, S_FLAG, OBS_TIME. Adapt parse step: no fixed-width "
          "parsing needed for this format, just unit conversion and pivot.")


if __name__ == "__main__":
    main()
