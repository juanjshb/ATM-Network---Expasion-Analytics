IF OBJECT_ID(N'dbo.atm_locations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.atm_locations (
        id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_atm_locations PRIMARY KEY,
        google_place_id VARCHAR(180) NOT NULL,
        bank VARCHAR(120) NOT NULL CONSTRAINT df_atm_locations_bank DEFAULT ('Scotiabank'),
        name VARCHAR(255) NOT NULL,
        address VARCHAR(600) NULL,
        province VARCHAR(120) NULL,
        region VARCHAR(120) NULL,
        country VARCHAR(120) NOT NULL CONSTRAINT df_atm_locations_country DEFAULT ('Dominican Republic'),
        latitude FLOAT NULL,
        longitude FLOAT NULL,
        business_status VARCHAR(80) NULL,
        google_maps_uri VARCHAR(1000) NULL,
        types VARCHAR(500) NULL,
        source_query VARCHAR(255) NOT NULL,
        raw_json NVARCHAR(MAX) NULL,
        first_seen_at DATETIME2 NOT NULL CONSTRAINT df_atm_locations_first_seen_at DEFAULT (SYSUTCDATETIME()),
        last_seen_at DATETIME2 NOT NULL CONSTRAINT df_atm_locations_last_seen_at DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT uq_atm_locations_google_place_id UNIQUE (google_place_id)
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_atm_locations_google_place_id'
      AND object_id = OBJECT_ID(N'dbo.atm_locations')
)
BEGIN
    CREATE INDEX ix_atm_locations_google_place_id
        ON dbo.atm_locations (google_place_id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_atm_locations_province'
      AND object_id = OBJECT_ID(N'dbo.atm_locations')
)
BEGIN
    CREATE INDEX ix_atm_locations_province
        ON dbo.atm_locations (province);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_atm_locations_region'
      AND object_id = OBJECT_ID(N'dbo.atm_locations')
)
BEGIN
    CREATE INDEX ix_atm_locations_region
        ON dbo.atm_locations (region);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_atm_locations_business_status'
      AND object_id = OBJECT_ID(N'dbo.atm_locations')
)
BEGIN
    CREATE INDEX ix_atm_locations_business_status
        ON dbo.atm_locations (business_status);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_atm_locations_last_seen_at'
      AND object_id = OBJECT_ID(N'dbo.atm_locations')
)
BEGIN
    CREATE INDEX ix_atm_locations_last_seen_at
        ON dbo.atm_locations (last_seen_at);
END
GO

IF OBJECT_ID(N'dbo.scrape_runs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.scrape_runs (
        id INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_scrape_runs PRIMARY KEY,
        query VARCHAR(255) NOT NULL,
        status VARCHAR(40) NOT NULL CONSTRAINT df_scrape_runs_status DEFAULT ('running'),
        result_count INT NOT NULL CONSTRAINT df_scrape_runs_result_count DEFAULT (0),
        inserted_count INT NOT NULL CONSTRAINT df_scrape_runs_inserted_count DEFAULT (0),
        updated_count INT NOT NULL CONSTRAINT df_scrape_runs_updated_count DEFAULT (0),
        error_message NVARCHAR(MAX) NULL,
        started_at DATETIME2 NOT NULL CONSTRAINT df_scrape_runs_started_at DEFAULT (SYSUTCDATETIME()),
        finished_at DATETIME2 NULL
    );
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_scrape_runs_status'
      AND object_id = OBJECT_ID(N'dbo.scrape_runs')
)
BEGIN
    CREATE INDEX ix_scrape_runs_status
        ON dbo.scrape_runs (status);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'ix_scrape_runs_started_at'
      AND object_id = OBJECT_ID(N'dbo.scrape_runs')
)
BEGIN
    CREATE INDEX ix_scrape_runs_started_at
        ON dbo.scrape_runs (started_at);
END
GO

