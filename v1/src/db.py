from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import Settings
from models import AtmLocation, Base, ScrapeRun


def create_db_engine(settings: Settings) -> Engine:
    settings.validate_database()
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)

    if settings.db_engine == "mssql":

        @event.listens_for(engine, "before_cursor_execute")
        def enable_fast_executemany(
            conn: Any,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: Any,
            executemany: bool,
        ) -> None:
            if executemany and hasattr(cursor, "fast_executemany"):
                cursor.fast_executemany = True

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def start_scrape_run(db: Session, query: str) -> ScrapeRun:
    run = ScrapeRun(query=query, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def finish_scrape_run(
    db: Session,
    run: ScrapeRun,
    *,
    status: str,
    result_count: int,
    inserted_count: int = 0,
    updated_count: int = 0,
    error_message: str | None = None,
) -> ScrapeRun:
    run.status = status
    run.result_count = result_count
    run.inserted_count = inserted_count
    run.updated_count = updated_count
    run.error_message = error_message
    run.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run


def upsert_atm_locations(
    db: Session,
    places: Iterable[dict[str, Any]],
    *,
    bank_name: str,
    country_name: str,
    source_query: str,
) -> tuple[int, int]:
    inserted = 0
    updated = 0

    for place in places:
        existing = db.scalar(
            select(AtmLocation).where(AtmLocation.google_place_id == place["google_place_id"])
        )
        payload = {
            "bank": bank_name,
            "name": place["name"],
            "address": place.get("address"),
            "province": place.get("province"),
            "region": place.get("region"),
            "country": country_name,
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "business_status": place.get("business_status"),
            "google_maps_uri": place.get("google_maps_uri"),
            "types": place.get("types"),
            "source_query": source_query,
            "raw_json": place.get("raw_json"),
        }

        if existing is None:
            db.add(AtmLocation(google_place_id=place["google_place_id"], **payload))
            inserted += 1
        else:
            for field, value in payload.items():
                setattr(existing, field, value)
            updated += 1

    db.commit()
    return inserted, updated

