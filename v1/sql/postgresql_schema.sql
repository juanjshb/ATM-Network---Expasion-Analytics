CREATE TABLE IF NOT EXISTS atm_locations (
    id SERIAL PRIMARY KEY,
    google_place_id VARCHAR(180) NOT NULL,
    bank VARCHAR(120) NOT NULL DEFAULT 'Scotiabank',
    name VARCHAR(255) NOT NULL,
    address VARCHAR(600),
    province VARCHAR(120),
    region VARCHAR(120),
    country VARCHAR(120) NOT NULL DEFAULT 'Dominican Republic',
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    business_status VARCHAR(80),
    google_maps_uri VARCHAR(1000),
    types VARCHAR(500),
    source_query VARCHAR(255) NOT NULL,
    raw_json TEXT,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_atm_locations_google_place_id UNIQUE (google_place_id)
);

CREATE INDEX IF NOT EXISTS ix_atm_locations_google_place_id
    ON atm_locations (google_place_id);

CREATE INDEX IF NOT EXISTS ix_atm_locations_province
    ON atm_locations (province);

CREATE INDEX IF NOT EXISTS ix_atm_locations_region
    ON atm_locations (region);

CREATE INDEX IF NOT EXISTS ix_atm_locations_business_status
    ON atm_locations (business_status);

CREATE INDEX IF NOT EXISTS ix_atm_locations_last_seen_at
    ON atm_locations (last_seen_at);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id SERIAL PRIMARY KEY,
    query VARCHAR(255) NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'running',
    result_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_scrape_runs_status
    ON scrape_runs (status);

CREATE INDEX IF NOT EXISTS ix_scrape_runs_started_at
    ON scrape_runs (started_at);

