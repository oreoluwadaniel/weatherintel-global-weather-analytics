# Database distribution

This repository ships the raw NOAA source files (`raw/data/`) and the parsed, staged CSVs (`staging/`), but not a built database file. The warehouse is PostgreSQL, built locally from those staging files. There's no single portable database file to distribute.

Build it locally with:

```bash
python pipeline/parse_and_stage.py
psql -d weatherintel -f sql/01_schema.sql
python pipeline/load_postgres.py
```

See the README's [Refreshing the data](README.md#refreshing-the-data) section for the full pipeline, including the NOAA refresh step and the QA/analysis SQL scripts.
