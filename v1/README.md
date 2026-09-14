# V1 - Google Places to SQL to Power BI

This version is intentionally simple:

1. Call Google Places Text Search API for Scotiabank ATMs in Dominican Republic.
2. Export results to CSV.
3. Upsert the same results into PostgreSQL or Microsoft SQL Server.
4. Connect Power BI to SQL views and build a dashboard inspired by the Scotia dark UI reference.

## Visual Target

The dashboard should follow the reference image:

- Dark background.
- Red Scotia accent.
- KPI cards at the top.
- Main geospatial map.
- Density bars by region/province.
- Detail table and scrape-run trend.

## Setup

```powershell
cd v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GOOGLE_API_KEY`.

## Choose Database

PostgreSQL:

```env
DB_ENGINE=postgresql
DATABASE_URL=postgresql+psycopg2://atm:atm_password@localhost:5432/atm_network_v1
```

Microsoft SQL Server:

```env
DB_ENGINE=mssql
DATABASE_URL=mssql+pyodbc://sa:YourStrong!Passw0rd@localhost:1433/atm_network_v1?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```

Optional local containers:

```powershell
docker compose up -d postgres
```

or:

```powershell
docker compose up -d mssql
```

If you use SQL Server, create the database once before running Python:

```powershell
sqlcmd -S localhost,1433 -U sa -P "YourStrong!Passw0rd" -C -i sql\create_mssql_database.sql
```

## Run Without Google Cost

```powershell
python src\main.py --dry-run
```

This creates a local CSV using sample rows and skips DB load by default.

To save the sample rows to the configured database:

```powershell
python src\main.py --dry-run --save-dry-run
```

## Run Google Places Load

```powershell
python src\main.py
```

Useful options:

```powershell
python src\main.py --query "Scotiabank ATM Republica Dominicana" --max-pages 3
python src\main.py --no-db
python src\main.py --csv data\custom_export.csv
```

The Google Text Search API supports `pageSize` up to 20. Pagination uses `nextPageToken` and `pageToken`.

If Google returns anything other than HTTP `200` or `201`, the loader now falls back to non-Google sources:

- Scotiabank Dominican Republic official location pages.
- `osm_scotiabank_candidates.json` in the repository root, when present.
- Synthetic test rows, when real fallback ATM rows are below the fallback target.

Fallback options:

```powershell
python src\main.py --no-fallback
python src\main.py --fallback-target 100
python src\main.py --fallback-osm-json ..\osm_scotiabank_candidates.json
python src\main.py --no-fallback-osm --no-fallback-synthetic
```

## SQL Views for Power BI

You can let the Python script create the tables automatically, or create them explicitly with SQL first.

Create tables in PostgreSQL:

```powershell
psql "postgresql://atm:atm_password@localhost:5432/atm_network_v1" -f sql\postgresql_schema.sql
```

Create tables in SQL Server:

```powershell
sqlcmd -S localhost,1433 -U sa -P "YourStrong!Passw0rd" -C -d atm_network_v1 -i sql\mssql_schema.sql
```

After the tables exist and the Python load has inserted data, create the Power BI views:

PostgreSQL:

```powershell
psql "postgresql://atm:atm_password@localhost:5432/atm_network_v1" -f sql\postgresql_views.sql
```

SQL Server:

```powershell
sqlcmd -S localhost,1433 -U sa -P "YourStrong!Passw0rd" -C -d atm_network_v1 -i sql\mssql_views.sql
```

## Power BI

1. Open Power BI Desktop.
2. Connect to PostgreSQL or SQL Server.
3. Load:
   - `v_atm_locations_powerbi`
   - `v_atm_kpis_powerbi`
   - `v_scrape_runs_powerbi`
4. Import `powerbi/scotia_dark_theme.json`.
5. Add measures from `powerbi/measures.dax`.
6. Follow `powerbi/dashboard_blueprint.md`.

## Notes

- Keep the Google field mask small to control cost.
- The script stores raw JSON for auditability.
- Province and region are inferred from names/addresses with simple rules in `src/geo.py`; adjust that mapping as you learn more from real results.
