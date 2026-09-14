from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from config import load_settings
from db import create_db_engine, create_session_factory, finish_scrape_run, start_scrape_run, upsert_atm_locations
from fallback_sources import build_fallback_places
from geo import infer_province_region
from google_places import PlacesApiError, search_text_places
from sample_data import SAMPLE_PLACES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Scotiabank ATM locations from Google Places into SQL.")
    parser.add_argument("--query", help="Google Places text query. Defaults to GOOGLE_PLACES_TEXT_QUERY.")
    parser.add_argument("--page-size", type=int, help="Results per Google page. Max supported by Google is 20.")
    parser.add_argument("--max-pages", type=int, help="Maximum Google pages to request. Text Search normally caps at 3.")
    parser.add_argument("--csv", type=Path, help="CSV export path.")
    parser.add_argument("--no-db", action="store_true", help="Skip database load and only export CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Use local sample rows and do not call Google.")
    parser.add_argument("--save-dry-run", action="store_true", help="Persist dry-run sample rows to the database.")
    parser.add_argument("--no-fallback", action="store_true", help="Fail instead of using fallback sources when Google returns a non-200/201 response.")
    parser.add_argument("--fallback-target", type=int, default=100, help="Minimum ATM rows to build when fallback synthetic rows are enabled.")
    parser.add_argument("--fallback-osm-json", type=Path, help="OSM candidate JSON path for the fallback loader.")
    parser.add_argument("--no-fallback-osm", action="store_true", help="Do not load OSM candidates during fallback.")
    parser.add_argument("--no-fallback-synthetic", action="store_true", help="Do not generate synthetic rows during fallback.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings()
    query = args.query or settings.text_query
    page_size = args.page_size or settings.page_size
    max_pages = args.max_pages or settings.max_pages
    output_csv = args.csv or settings.output_csv

    if args.dry_run:
        places = [_with_geo_hints(place) for place in SAMPLE_PLACES]
        print("Dry run: using local sample data. No Google API call was made.")
    else:
        settings.validate_google_key()
        try:
            places = search_text_places(
                api_key=settings.google_api_key,
                query=query,
                field_mask=settings.field_mask,
                page_size=page_size,
                max_pages=max_pages,
                delay_seconds=settings.request_delay_seconds,
                timeout_seconds=settings.timeout_seconds,
            )
        except PlacesApiError as exc:
            if args.no_fallback:
                print(str(exc), file=sys.stderr)
                return 1

            print(str(exc), file=sys.stderr)
            print("Using fallback sources because Google did not return 200/201.", file=sys.stderr)
            places = build_fallback_places(
                target_count=args.fallback_target,
                osm_json_path=args.fallback_osm_json,
                include_osm=not args.no_fallback_osm,
                include_synthetic=not args.no_fallback_synthetic,
                timeout_seconds=settings.timeout_seconds,
                delay_seconds=settings.request_delay_seconds,
            )
            if not places:
                print("Fallback did not produce any ATM rows.", file=sys.stderr)
                return 1
            print(f"Fallback produced {len(places)} ATM rows.", file=sys.stderr)

    export_csv(places, output_csv)

    should_skip_db = args.no_db or (args.dry_run and not args.save_dry_run)
    if should_skip_db:
        print(f"Completed: {len(places)} locations exported to {output_csv}. Database load skipped.")
        return 0

    try:
        engine = create_db_engine(settings)
        session_factory = create_session_factory(engine)
        with session_factory() as db:
            run = start_scrape_run(db, query)
            try:
                inserted, updated = upsert_atm_locations(
                    db,
                    places,
                    bank_name=settings.bank_name,
                    country_name=settings.country_name,
                    source_query=query,
                )
                finish_scrape_run(
                    db,
                    run,
                    status="success",
                    result_count=len(places),
                    inserted_count=inserted,
                    updated_count=updated,
                )
            except Exception as exc:
                finish_scrape_run(db, run, status="failed", result_count=len(places), error_message=str(exc))
                raise
    except (SQLAlchemyError, ValueError) as exc:
        print(
            f"CSV exported to {output_csv}, but database load failed: {exc}",
            file=sys.stderr,
        )
        print(
            "Fix DB_ENGINE/DATABASE_URL in v1/.env or run with --no-db to skip the database load.",
            file=sys.stderr,
        )
        return 1

    print(
        "Completed: "
        f"{len(places)} locations processed, {inserted} inserted, {updated} updated, "
        f"CSV exported to {output_csv}."
    )
    return 0


def export_csv(places: list[dict], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "google_place_id",
        "name",
        "address",
        "province",
        "region",
        "latitude",
        "longitude",
        "business_status",
        "google_maps_uri",
        "types",
        "raw_json",
    ]
    with output_csv.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(places)


def _with_geo_hints(place: dict) -> dict:
    province, region = infer_province_region(place.get("name"), place.get("address"))
    return {**place, "province": province, "region": region}


if __name__ == "__main__":
    raise SystemExit(main())
