from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import time
import unicodedata

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURATION
# =========================================================

SCOTIABANK_URL = (
    "https://do.scotiabank.com/"
    "acerca-de-scotiabank/"
    "conectate-con-scotia/"
    "sucursales-y-atms.html"
)

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

OUTPUT_DIR = Path("data")

CACHE_FILE = (
    OUTPUT_DIR / "nominatim_cache.json"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# IMPORTANT:
# Put a real contact email in your environment if possible:
#
# Windows PowerShell:
#
# $env:NOMINATIM_CONTACT_EMAIL="your@email.com"
#

CONTACT_EMAIL = os.getenv(
    "NOMINATIM_CONTACT_EMAIL",
    "",
)


HEADERS = {
    "User-Agent": (
        "ATM-Network-Expansion-Analytics/2.0 "
        f"(research project; contact={CONTACT_EMAIL or 'local-development'})"
    ),
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}


# Nominatim public API policy:
# absolute maximum 1 request/second.
#
GEOCODE_DELAY_SECONDS = 1.1

GEOCODE_TIMEOUT = 30

GEOCODE_RETRIES = 3


# =========================================================
# CLI
# =========================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Extract and geocode Scotiabank branches "
            "and intelligent ATMs in Dominican Republic."
        )
    )

    parser.add_argument(
        "--no-geocode",
        action="store_true",
        help="Extract locations without geocoding.",
    )

    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore previous Nominatim cache.",
    )

    return parser.parse_args()


# =========================================================
# TEXT UTILITIES
# =========================================================

def clean_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_text(
    value: str | None,
) -> str:

    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return value.strip()


def normalize_location_name(
    value: str | None,
) -> str:

    value = normalize_text(
        value
    )

    # Remove words that do not help us match
    # ATM names against branch names.

    stop_words = {
        "scotiabank",
        "atm",
        "cajero",
        "cajeros",
        "inteligente",
        "inteligentes",
        "sucursal",
        "branch",
    }

    words = [
        word
        for word in value.split()
        if word not in stop_words
    ]

    return " ".join(
        words
    )


def make_id(
    *values: Any,
) -> str:

    raw = "|".join(
        str(value or "")
        for value in values
    )

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:16]


# =========================================================
# HTTP
# =========================================================

def get_scotiabank_page(
    session: requests.Session,
) -> BeautifulSoup:

    print()
    print(
        "Downloading Scotiabank official location data..."
    )

    response = session.get(
        SCOTIABANK_URL,
        timeout=30,
    )

    print(
        f"HTTP: {response.status_code}"
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


# =========================================================
# BRANCH EXTRACTION
# =========================================================

def extract_branch_tables(
    soup: BeautifulSoup,
) -> list[dict]:

    results = []

    current_zone = ""

    for element in soup.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
            "table",
        ]
    ):

        # -------------------------------------------------
        # Zone
        # -------------------------------------------------

        if element.name != "table":

            text = clean_text(
                element.get_text()
            )

            if text.lower().startswith(
                "zona "
            ):
                current_zone = text

            continue

        # -------------------------------------------------
        # Table
        # -------------------------------------------------

        headers = [
            clean_text(
                th.get_text()
            ).lower()
            for th in element.find_all("th")
        ]

        if "nombre" not in headers:
            continue

        for row in element.find_all(
            "tr"
        ):

            cells = [
                clean_text(
                    td.get_text()
                )
                for td in row.find_all(
                    "td"
                )
            ]

            if len(cells) < 2:
                continue

            name = cells[0]

            if (
                "scotiabank"
                not in name.lower()
            ):
                continue

            address = (
                cells[1]
                if len(cells) > 1
                else ""
            )

            phone = (
                cells[2]
                if len(cells) > 2
                else ""
            )

            results.append(
                {
                    "record_id":
                        make_id(
                            "branch",
                            name,
                            address,
                        ),

                    "bank":
                        "Scotiabank",

                    "location_type":
                        "branch",

                    "name":
                        name,

                    "province":
                        "",

                    "zone":
                        current_zone,

                    "address":
                        address,

                    "phone":
                        phone,

                    "matched_branch":
                        "",

                    "branch_match_score":
                        None,

                    "latitude":
                        None,

                    "longitude":
                        None,

                    "geocoded_address":
                        "",

                    "geocode_query":
                        "",

                    "geocode_quality":
                        "",

                    "coordinate_source":
                        "",

                    "source":
                        "scotiabank_official",

                    "source_url":
                        SCOTIABANK_URL,

                    "is_synthetic":
                        False,
                }
            )

    return results


# =========================================================
# ATM EXTRACTION
# =========================================================

def find_atm_heading(
    soup: BeautifulSoup,
):

    for tag in soup.find_all(
        [
            "h2",
            "h3",
            "h4",
            "h5",
        ]
    ):

        text = normalize_text(
            tag.get_text()
        )

        if (
            "ubicacion de cajeros inteligentes"
            in text
        ):
            return tag

    return None


def extract_intelligent_atms(
    soup: BeautifulSoup,
) -> list[dict]:

    results = []

    heading = find_atm_heading(
        soup
    )

    if heading is None:

        print(
            "WARNING: ATM section not found."
        )

        return results

    current_province = ""

    # Iterate through sibling content after
    # "Ubicación de Cajeros Inteligentes"

    element = heading.find_next()

    while element:

        text = clean_text(
            element.get_text()
        )

        # -------------------------------------------------
        # Stop when reaching next major section
        # -------------------------------------------------

        normalized = normalize_text(
            text
        )

        if (
            element.name in {"h2", "h3"}
            and
            element != heading
            and
            (
                "canales digitales"
                in normalized
                or
                "necesitas mas informacion"
                in normalized
            )
        ):
            break

        # -------------------------------------------------
        # Province
        # -------------------------------------------------

        if element.name in {
            "h4",
            "h5",
            "h6",
        }:

            if text:
                current_province = text

        # -------------------------------------------------
        # ATM
        # -------------------------------------------------

        elif element.name == "li":

            name = text

            if name:

                results.append(
                    {
                        "record_id":
                            make_id(
                                "atm",
                                current_province,
                                name,
                            ),

                        "bank":
                            "Scotiabank",

                        "location_type":
                            "intelligent_atm",

                        "name":
                            name,

                        "province":
                            current_province,

                        "zone":
                            "",

                        "address":
                            "",

                        "phone":
                            "",

                        "matched_branch":
                            "",

                        "branch_match_score":
                            None,

                        "latitude":
                            None,

                        "longitude":
                            None,

                        "geocoded_address":
                            "",

                        "geocode_query":
                            "",

                        "geocode_quality":
                            "",

                        "coordinate_source":
                            "",

                        "source":
                            "scotiabank_official",

                        "source_url":
                            SCOTIABANK_URL,

                        "is_synthetic":
                            False,
                    }
                )

        element = element.find_next()

    return results


# =========================================================
# ATM → BRANCH MATCHING
# =========================================================

def similarity_score(
    first: str,
    second: str,
) -> float:

    first = normalize_location_name(
        first
    )

    second = normalize_location_name(
        second
    )

    if not first or not second:
        return 0.0

    # Exact containment is strong evidence.

    if (
        first in second
        or second in first
    ):
        return 0.95

    return SequenceMatcher(
        None,
        first,
        second,
    ).ratio()


def match_atms_to_branches(
    atms: list[dict],
    branches: list[dict],
) -> None:

    print()
    print(
        "Matching intelligent ATMs "
        "against official branches..."
    )

    matched = 0

    for atm in atms:

        best_branch = None
        best_score = 0.0

        for branch in branches:

            score = similarity_score(
                atm["name"],
                branch["name"],
            )

            if score > best_score:

                best_score = score
                best_branch = branch

        # Conservative threshold.
        #
        # Do not assign questionable branch addresses.

        if (
            best_branch
            and best_score >= 0.68
        ):

            atm["matched_branch"] = (
                best_branch["name"]
            )

            atm[
                "branch_match_score"
            ] = round(
                best_score,
                3,
            )

            atm["address"] = (
                best_branch["address"]
            )

            atm["phone"] = (
                best_branch["phone"]
            )

            atm["zone"] = (
                best_branch["zone"]
            )

            matched += 1

    print(
        f"ATM matched with branches: "
        f"{matched}/{len(atms)}"
    )


# =========================================================
# NOMINATIM CACHE
# =========================================================

def load_cache() -> dict:

    if not CACHE_FILE.exists():
        return {}

    try:

        with CACHE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return {}


def save_cache(
    cache: dict,
) -> None:

    with CACHE_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False,
        )


# =========================================================
# GEOCODING
# =========================================================

def query_nominatim(
    session: requests.Session,
    query: str,
    cache: dict,
) -> dict | None:

    cache_key = normalize_text(
        query
    )

    if cache_key in cache:

        return cache[
            cache_key
        ]

    params = {
        "q":
            query,

        "format":
            "jsonv2",

        "countrycodes":
            "do",

        "limit":
            1,

        "addressdetails":
            1,

        "namedetails":
            1,

        "accept-language":
            "es",
    }

    if CONTACT_EMAIL:

        params["email"] = (
            CONTACT_EMAIL
        )

    for attempt in range(
        1,
        GEOCODE_RETRIES + 1,
    ):

        try:

            response = session.get(
                NOMINATIM_URL,
                params=params,
                timeout=GEOCODE_TIMEOUT,
            )

            if response.status_code == 200:

                data = response.json()

                result = (
                    data[0]
                    if data
                    else None
                )

                cache[
                    cache_key
                ] = result

                save_cache(
                    cache
                )

                # Respect public API policy.
                time.sleep(
                    GEOCODE_DELAY_SECONDS
                )

                return result

            if response.status_code in {
                429,
                502,
                503,
                504,
            }:

                print(
                    f"   Temporary geocoder "
                    f"error {response.status_code}"
                )

                time.sleep(
                    max(
                        GEOCODE_DELAY_SECONDS,
                        attempt * 2,
                    )
                )

                continue

            response.raise_for_status()

        except requests.RequestException as exc:

            print(
                f"   Geocoder error: {exc}"
            )

            time.sleep(
                max(
                    GEOCODE_DELAY_SECONDS,
                    attempt * 2,
                )
            )

    cache[
        cache_key
    ] = None

    save_cache(
        cache
    )

    return None


def build_geocode_queries(
    row: dict,
) -> list[
    tuple[str, str]
]:

    queries = []

    name = clean_text(
        row.get("name")
    )

    address = clean_text(
        row.get("address")
    )

    province = clean_text(
        row.get("province")
    )

    location_type = row.get(
        "location_type"
    )

    # -----------------------------------------------------
    # Highest-quality query:
    # known official branch address
    # -----------------------------------------------------

    if address:

        queries.append(
            (
                (
                    f"{address}, "
                    "República Dominicana"
                ),
                "official_address",
            )
        )

        queries.append(
            (
                (
                    f"{name}, "
                    f"{address}, "
                    "República Dominicana"
                ),
                "name_and_address",
            )
        )

    # -----------------------------------------------------
    # Intelligent ATM location + province
    # -----------------------------------------------------

    if (
        location_type
        == "intelligent_atm"
    ):

        if province:

            queries.append(
                (
                    (
                        f"{name}, "
                        f"{province}, "
                        "República Dominicana"
                    ),
                    "atm_name_province",
                )
            )

            queries.append(
                (
                    (
                        f"Scotiabank {name}, "
                        f"{province}, "
                        "República Dominicana"
                    ),
                    "bank_atm_name_province",
                )
            )

        else:

            queries.append(
                (
                    (
                        f"{name}, "
                        "República Dominicana"
                    ),
                    "atm_name",
                )
            )

    # -----------------------------------------------------
    # Generic final fallback
    # -----------------------------------------------------

    queries.append(
        (
            (
                f"{name}, "
                "República Dominicana"
            ),
            "name_country",
        )
    )

    # Remove duplicate queries

    unique = []

    seen = set()

    for query, quality in queries:

        key = normalize_text(
            query
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            (
                query,
                quality,
            )
        )

    return unique


def apply_geocode_result(
    row: dict,
    result: dict,
    query: str,
    quality: str,
) -> None:

    row["latitude"] = float(
        result["lat"]
    )

    row["longitude"] = float(
        result["lon"]
    )

    row["geocoded_address"] = (
        result.get(
            "display_name",
            "",
        )
    )

    row["geocode_query"] = (
        query
    )

    row["geocode_quality"] = (
        quality
    )

    row["coordinate_source"] = (
        "openstreetmap_nominatim"
    )

    row["osm_type"] = (
        result.get("osm_type")
    )

    row["osm_id"] = (
        result.get("osm_id")
    )

    row["osm_importance"] = (
        result.get("importance")
    )


def geocode_rows(
    rows: list[dict],
    session: requests.Session,
    cache: dict,
) -> None:

    print()
    print(
        "=" * 72
    )

    print(
        "GEOCODING LOCATIONS"
    )

    print(
        "=" * 72
    )

    total = len(rows)

    found = 0

    for index, row in enumerate(
        rows,
        start=1,
    ):

        print()
        print(
            f"[{index}/{total}] "
            f"{row['name']}"
        )

        queries = build_geocode_queries(
            row
        )

        geocoded = False

        for query, quality in queries:

            print(
                f"   Searching: {query}"
            )

            result = query_nominatim(
                session,
                query,
                cache,
            )

            if not result:

                print(
                    "   → no result"
                )

                continue

            apply_geocode_result(
                row,
                result,
                query,
                quality,
            )

            print(
                "   → "
                f"{row['latitude']}, "
                f"{row['longitude']}"
            )

            print(
                "   → "
                f"{row['geocoded_address']}"
            )

            geocoded = True
            found += 1

            break

        if not geocoded:

            row[
                "geocode_quality"
            ] = "not_found"

            print(
                "   → LOCATION NOT FOUND"
            )

    print()
    print(
        f"Geocoded: {found}/{total}"
    )

    print(
        f"Missing  : {total - found}/{total}"
    )


# =========================================================
# CSV
# =========================================================

CSV_COLUMNS = [
    "record_id",
    "bank",
    "location_type",
    "name",
    "province",
    "zone",
    "address",
    "phone",
    "matched_branch",
    "branch_match_score",
    "latitude",
    "longitude",
    "geocoded_address",
    "geocode_query",
    "geocode_quality",
    "coordinate_source",
    "osm_type",
    "osm_id",
    "osm_importance",
    "source",
    "source_url",
    "is_synthetic",
]


def export_csv(
    rows: list[dict],
    filename: str,
) -> None:

    filepath = (
        OUTPUT_DIR / filename
    )

    with filepath.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            rows
        )

    print(
        f"{len(rows)} rows → "
        f"{filepath}"
    )


# =========================================================
# SUMMARY
# =========================================================

def print_summary(
    branches: list[dict],
    atms: list[dict],
) -> None:

    all_rows = (
        branches
        + atms
    )

    geocoded = [
        row
        for row in all_rows
        if (
            row.get("latitude")
            is not None
            and
            row.get("longitude")
            is not None
        )
    ]

    atm_geocoded = [
        row
        for row in atms
        if (
            row.get("latitude")
            is not None
            and
            row.get("longitude")
            is not None
        )
    ]

    matched = [
        row
        for row in atms
        if row.get(
            "matched_branch"
        )
    ]

    print()
    print(
        "=" * 72
    )

    print(
        "ATM NETWORK - EXTRACTION SUMMARY"
    )

    print(
        "=" * 72
    )

    print(
        f"Branches found       : "
        f"{len(branches)}"
    )

    print(
        f"Intelligent ATMs     : "
        f"{len(atms)}"
    )

    print(
        f"ATM → branch matches : "
        f"{len(matched)}"
    )

    print(
        f"ATM with coordinates : "
        f"{len(atm_geocoded)}"
    )

    print(
        f"All geocoded rows    : "
        f"{len(geocoded)}"
    )

    print(
        f"Rows total           : "
        f"{len(all_rows)}"
    )

    print(
        "=" * 72
    )


# =========================================================
# MAIN
# =========================================================

def main() -> int:

    args = parse_args()

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # -----------------------------------------------------
    # Download official data
    # -----------------------------------------------------

    soup = get_scotiabank_page(
        session
    )

    # -----------------------------------------------------
    # Extract
    # -----------------------------------------------------

    branches = extract_branch_tables(
        soup
    )

    atms = extract_intelligent_atms(
        soup
    )

    print()
    print(
        f"Branches extracted: "
        f"{len(branches)}"
    )

    print(
        f"Intelligent ATMs extracted: "
        f"{len(atms)}"
    )

    # -----------------------------------------------------
    # Match ATM names against official branches
    # -----------------------------------------------------

    match_atms_to_branches(
        atms,
        branches,
    )

    # -----------------------------------------------------
    # Geocode
    # -----------------------------------------------------

    if not args.no_geocode:

        if args.refresh_cache:

            cache = {}

        else:

            cache = load_cache()

        geocode_rows(
            branches + atms,
            session,
            cache,
        )

    # -----------------------------------------------------
    # Export
    # -----------------------------------------------------

    export_csv(
        branches,
        "scotiabank_branches_geocoded.csv",
    )

    export_csv(
        atms,
        "scotiabank_atms_geocoded.csv",
    )

    export_csv(
        branches + atms,
        "scotiabank_locations_master.csv",
    )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print_summary(
        branches,
        atms,
    )

    print()
    print(
        "OpenStreetMap attribution:"
    )

    print(
        "© OpenStreetMap contributors"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )