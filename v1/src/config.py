from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


V1_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.businessStatus,"
    "places.googleMapsUri,"
    "places.types,"
    "nextPageToken"
)


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    text_query: str
    page_size: int
    max_pages: int
    request_delay_seconds: float
    timeout_seconds: float
    db_engine: str
    database_url: str
    output_csv: Path
    bank_name: str
    country_name: str
    field_mask: str = DEFAULT_FIELD_MASK

    def validate_database(self) -> None:
        expected_prefixes = {
            "postgresql": ("postgresql://", "postgresql+"),
            "mssql": ("mssql://", "mssql+"),
        }
        prefixes = expected_prefixes.get(self.db_engine)
        if prefixes is None:
            raise ValueError("DB_ENGINE must be 'postgresql' or 'mssql'.")
        if not self.database_url.lower().startswith(prefixes):
            expected = " or ".join(prefixes)
            raise ValueError(f"DATABASE_URL must start with {expected} for DB_ENGINE={self.db_engine}.")

    def validate_google_key(self) -> None:
        if not self.google_api_key or self.google_api_key == "TU_API_KEY_AQUI":
            raise ValueError("Set GOOGLE_API_KEY in v1/.env before calling Google Places API.")


def load_settings() -> Settings:
    load_dotenv(V1_ROOT / ".env")
    load_dotenv(Path.cwd() / ".env", override=True)

    return Settings(
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        text_query=os.getenv("GOOGLE_PLACES_TEXT_QUERY", "Scotiabank ATM Republica Dominicana"),
        page_size=int(os.getenv("GOOGLE_PLACES_PAGE_SIZE", "20")),
        max_pages=int(os.getenv("GOOGLE_PLACES_MAX_PAGES", "3")),
        request_delay_seconds=float(os.getenv("GOOGLE_PLACES_REQUEST_DELAY_SECONDS", "2")),
        timeout_seconds=float(os.getenv("GOOGLE_PLACES_TIMEOUT_SECONDS", "30")),
        db_engine=os.getenv("DB_ENGINE", "postgresql").lower().strip(),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://atm:atm_password@localhost:5432/atm_network_v1",
        ),
        output_csv=V1_ROOT / os.getenv("OUTPUT_CSV", "data/cajeros_scotiabank_rd_google.csv"),
        bank_name=os.getenv("BANK_NAME", "Scotiabank"),
        country_name=os.getenv("COUNTRY_NAME", "Dominican Republic"),
        field_mask=os.getenv("GOOGLE_PLACES_FIELD_MASK", DEFAULT_FIELD_MASK),
    )

