# Power BI Dashboard Blueprint

Use the reference image as a guide, but keep v1 simple and connected directly to SQL.

## Layout

1. Header
   - Title: ATM Network Expansion & Geospatial Analytics
   - Subtitle: Dominican Republic
   - Slicers: region, province, business_status

2. KPI row
   - Total ATMs
   - Operational ATMs
   - Provinces Covered
   - Last Refresh

3. Main map
   - Visual: Azure Maps or Map
   - Latitude: latitude
   - Longitude: longitude
   - Legend: region
   - Tooltip: name, address, province, business_status, google_maps_uri

4. Right column
   - Bar chart: Total ATMs by region
   - Bar chart: Total ATMs by province

5. Bottom section
   - Table: name, address, province, region, google_maps_uri
   - Line chart: scrape_runs result_count by started_at

## Style

- Import `scotia_dark_theme.json`.
- Page background: `#111217`.
- Visual background: `#202127`.
- Main accent: `#D9203A`.
- Text: `#F6F7FB`.
- Use compact cards and avoid large white spaces.

