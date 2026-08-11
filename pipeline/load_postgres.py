"""
load_postgres.py  (Milestone 3: loading the warehouse)

Bulk-loads the staging CSVs into PostgreSQL using COPY, the fastest and most
professional load path (10 to 50x faster than row-by-row INSERTs).

BEFORE RUNNING: edit DB_URL below with your own postgres user and password.
Run:  python pipeline/load_postgres.py
Requires: pip install psycopg2-binary
"""
import psycopg2

# >>> EDIT THIS LINE with your credentials <<<
DB_URL = "postgresql://postgres:postgres@localhost:5432/weatherintel"

LOADS = [
    ("dim_station", "staging/dim_station.csv"),
    ("dim_date", "staging/dim_date.csv"),
    ("dim_element", "staging/dim_element.csv"),
    ("fact_weather_observations", "staging/fact_observations_long.csv"),
    ("fact_daily_weather", "staging/fact_daily_weather.csv"),
]
# Load order matters: dimensions first, because the facts hold foreign keys
# that reference them. Reverse the order and Postgres rejects every fact row.


def main():
    con = psycopg2.connect(DB_URL)
    cur = con.cursor()
    for table, path in LOADS:
        with open(path) as f:
            header = f.readline().strip()          # column list from the CSV itself
            cur.copy_expert(
                f"COPY {table} ({header}) FROM STDIN WITH (FORMAT csv, NULL '')", f)
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table:32s} {cur.fetchone()[0]:>12,} rows loaded")
    con.commit()
    cur.execute("ANALYZE;")   # refresh planner statistics after a bulk load
    con.commit()
    con.close()
    print("Load complete.")


if __name__ == "__main__":
    main()
