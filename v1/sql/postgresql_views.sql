CREATE OR REPLACE VIEW v_atm_locations_powerbi
AS
SELECT
    id,
    google_place_id,
    bank,
    name,
    address,
    province,
    region,
    country,
    latitude,
    longitude,
    business_status,
    google_maps_uri,
    source_query,
    first_seen_at,
    last_seen_at,

    -- Random transaction count:
    -- Minimum: 50
    -- Maximum: 10,000,000
    FLOOR(
        50 + RANDOM() * (10000000 - 50 + 1)
    )::BIGINT AS transaction_count

FROM public.atm_locations;

CREATE OR REPLACE VIEW v_atm_kpis_powerbi AS
SELECT
    COUNT(*) AS total_atms,
    COUNT(DISTINCT province) AS provinces_covered,
    COUNT(DISTINCT region) AS regions_covered,
    MAX(last_seen_at) AS last_refresh_at
FROM atm_locations;

CREATE OR REPLACE VIEW v_scrape_runs_powerbi AS
SELECT
    id,
    query,
    status,
    result_count,
    inserted_count,
    updated_count,
    started_at,
    finished_at
FROM scrape_runs;

