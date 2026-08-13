import psycopg2
DB_URL = "postgresql://postgres:postgres@localhost:5432/weatherintel"

LOADS = [
    ("dim_station", "staging/dim_station.csv"),
    ("dim_date", "staging/dim_date.csv"),
    ("dim_element", "staging/dim_element.csv"),
    ("fact_weather_observations", "staging/fact_observations_long.csv"),
    ("fact_daily_weather", "staging/fact_daily_weather.csv"),
]
def main():
    con = psycopg2.connect(DB_URL)
    cur = con.cursor()
    for table, path in LOADS:
        with open(path) as f:
            header = f.readline().strip()          
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
