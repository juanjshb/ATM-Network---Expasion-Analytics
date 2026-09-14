from __future__ import annotations

import hashlib
import json
import random
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from geo import infer_province_region


OFFICIAL_URLS = [
    (
        "https://do.scotiabank.com/"
        "acerca-de-scotiabank/"
        "conectate-con-scotia/"
        "sucursales-y-atms.html"
    ),
    (
        "https://do.scotiabank.com/"
        "banca-personal/"
        "canales-alternos/"
        "cajeros-automaticos.html"
    ),
]

DEFAULT_OSM_JSON = Path(__file__).resolve().parents[2] / "osm_scotiabank_candidates.json"

FALLBACK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(ATM-Network-Expansion-Analytics/2.0; research-development)"
    ),
    "Accept-Language": "es-DO,es;q=0.9,en;q=0.8",
}

ATM_TYPES = {
    "intelligent_atm",
    "direct_scotiabank_atm",
    "near_scotiabank_branch",
    "scotiabank_branch_with_atm",
    "standalone_atm",
    "osm_candidate",
    "synthetic_atm",
}


def build_fallback_places(
    *,
    target_count: int = 100,
    osm_json_path: Path | None = None,
    include_osm: bool = True,
    include_synthetic: bool = True,
    seed: int = 42,
    timeout_seconds: float = 30,
    delay_seconds: float = 1.5,
) -> list[dict[str, Any]]:
    """Build Google-compatible ATM rows from non-Google fallback sources."""

    official_rows = fetch_official_rows(
        timeout_seconds=timeout_seconds,
        delay_seconds=delay_seconds,
    )

    osm_rows: list[dict[str, Any]] = []
    if include_osm:
        osm_rows = load_osm_candidates(osm_json_path or DEFAULT_OSM_JSON)

    real_rows = deduplicate(official_rows + osm_rows)
    real_atms = [row for row in real_rows if is_atm_candidate(row)]

    synthetic_rows: list[dict[str, Any]] = []
    if include_synthetic and len(real_atms) < target_count:
        synthetic_rows = generate_synthetic_atms(
            real_rows,
            target_count=target_count,
            seed=seed,
        )

    return [
        to_google_compatible_place(row)
        for row in deduplicate(real_atms + synthetic_rows)
    ]


def fetch_official_rows(
    *,
    timeout_seconds: float,
    delay_seconds: float,
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(FALLBACK_HEADERS)

    rows: list[dict[str, Any]] = []
    for index, url in enumerate(OFFICIAL_URLS):
        try:
            soup = get_page(session, url, timeout_seconds=timeout_seconds)
        except requests.RequestException as exc:
            print(f"Fallback skipped official URL {url}: {exc}")
            continue

        rows.extend(extract_branch_tables(soup, url))
        rows.extend(extract_intelligent_atms(soup, url))

        if index < len(OFFICIAL_URLS) - 1:
            time.sleep(delay_seconds)

    return deduplicate(rows)


def get_page(
    session: requests.Session,
    url: str,
    *,
    timeout_seconds: float,
) -> BeautifulSoup:
    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_branch_tables(
    soup: BeautifulSoup,
    source_url: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    current_zone = ""
    elements = soup.find_all(["h2", "h3", "h4", "h5", "h6", "table"])

    for element in elements:
        if element.name != "table":
            text = clean_text(element.get_text())
            if text.lower().startswith("zona "):
                current_zone = text
            continue

        headers = [
            clean_text(th.get_text()).lower()
            for th in element.find_all("th")
        ]
        if "nombre" not in headers:
            continue

        for row in element.find_all("tr"):
            cells = [
                clean_text(td.get_text())
                for td in row.find_all("td")
            ]
            if len(cells) < 2:
                continue

            name = cells[0]
            if "scotiabank" not in name.lower():
                continue

            address = cells[1]
            phone = cells[2] if len(cells) >= 3 else ""

            results.append(
                {
                    "record_id": make_id("official", "branch", name, address),
                    "bank": "Scotiabank",
                    "location_type": "branch",
                    "name": name,
                    "province": "",
                    "zone": current_zone,
                    "address": address,
                    "phone": phone,
                    "latitude": None,
                    "longitude": None,
                    "osm_id": None,
                    "confidence": 100,
                    "source": "scotiabank_official",
                    "source_url": source_url,
                    "is_synthetic": False,
                }
            )

    return results


def extract_intelligent_atms(
    soup: BeautifulSoup,
    source_url: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    heading = find_atm_heading(soup)
    if heading is None:
        return results

    current_province = ""
    for element in heading.find_all_next(["h2", "h3", "h4", "h5", "h6", "li"]):
        if element != heading and element.name in {"h2", "h3"}:
            break

        if element.name in {"h4", "h5", "h6"}:
            text = clean_text(element.get_text())
            if text:
                current_province = text
            continue

        if element.name != "li":
            continue

        name = clean_text(element.get_text())
        if not name:
            continue

        results.append(
            {
                "record_id": make_id(
                    "official",
                    "intelligent_atm",
                    current_province,
                    name,
                ),
                "bank": "Scotiabank",
                "location_type": "intelligent_atm",
                "name": name,
                "province": current_province,
                "zone": "",
                "address": "",
                "phone": "",
                "latitude": None,
                "longitude": None,
                "osm_id": None,
                "confidence": 100,
                "source": "scotiabank_official",
                "source_url": source_url,
                "is_synthetic": False,
            }
        )

    return results


def find_atm_heading(soup: BeautifulSoup) -> Any:
    for tag in soup.find_all(["h2", "h3", "h4", "h5"]):
        text = normalize_text(tag.get_text())
        if (
            "cajeros inteligentes" in text
            or "ubicacion de cajeros inteligentes" in text
        ):
            return tag
    return None


def load_osm_candidates(filepath: Path) -> list[dict[str, Any]]:
    if not filepath.exists():
        print(f"Fallback OSM file not found: {filepath}")
        return []

    with filepath.open("r", encoding="utf-8") as file:
        data = json.load(file)

    rows: list[dict[str, Any]] = []
    for item in data:
        location_type = item.get("location_type", "osm_candidate")
        if location_type == "scotiabank_branch_without_atm":
            continue

        osm_id = f"{item.get('osm_type')}/{item.get('osm_id')}"
        rows.append(
            {
                "record_id": make_id("osm", osm_id),
                "bank": "Scotiabank",
                "location_type": location_type,
                "name": item.get("name") or "Scotiabank ATM",
                "province": item.get("province", ""),
                "zone": "",
                "address": item.get("address", ""),
                "phone": "",
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "osm_id": osm_id,
                "confidence": item.get("confidence", 70),
                "source": "openstreetmap",
                "source_url": "",
                "is_synthetic": False,
            }
        )

    return rows


def generate_synthetic_atms(
    real_rows: list[dict[str, Any]],
    *,
    target_count: int,
    seed: int,
) -> list[dict[str, Any]]:
    random.seed(seed)
    current_atms = [row for row in real_rows if is_atm_candidate(row)]
    missing = target_count - len(current_atms)
    if missing <= 0:
        return []

    templates = current_atms.copy()
    if not templates:
        templates = [
            row
            for row in real_rows
            if row.get("location_type") == "branch"
        ]
    if not templates:
        return []

    synthetic: list[dict[str, Any]] = []
    for index in range(1, missing + 1):
        base = random.choice(templates)
        lat = base.get("latitude")
        lon = base.get("longitude")
        synthetic_lat = None
        synthetic_lon = None

        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            synthetic_lat = round(lat + random.uniform(-0.004, 0.004), 7)
            synthetic_lon = round(lon + random.uniform(-0.004, 0.004), 7)

        synthetic.append(
            {
                "record_id": make_id("synthetic", seed, index),
                "bank": "Scotiabank",
                "location_type": "synthetic_atm",
                "name": f"Scotiabank ATM TEST-{index:03d}",
                "province": base.get("province", ""),
                "zone": base.get("zone", ""),
                "address": f"TEST DATA - based on {base.get('name', '')}",
                "phone": "",
                "latitude": synthetic_lat,
                "longitude": synthetic_lon,
                "osm_id": None,
                "confidence": 0,
                "source": "synthetic_test",
                "source_url": "",
                "is_synthetic": True,
                "synthetic_parent_id": base.get("record_id"),
            }
        )

    return synthetic


def to_google_compatible_place(row: dict[str, Any]) -> dict[str, Any]:
    name = row.get("name") or "Scotiabank ATM"
    address = row.get("address") or row.get("zone") or ""
    province = row.get("province") or None
    inferred_province, region = infer_province_region(
        name,
        address,
        province,
        row.get("zone"),
    )

    province = province or inferred_province
    row_for_audit = {**row, "fallback_schema": "scotiabank_atm_v1"}
    source = row.get("source") or "fallback"
    location_type = row.get("location_type") or "atm"

    return {
        "google_place_id": f"fallback-{row['record_id']}",
        "name": name,
        "address": address,
        "province": province,
        "region": region,
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "business_status": "OPERATIONAL" if not row.get("is_synthetic") else None,
        "google_maps_uri": None,
        "types": f"atm,finance,point_of_interest,{source},{location_type}",
        "raw_json": json.dumps(row_for_audit, ensure_ascii=True),
    }


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = duplicate_key(row)
        if key not in unique:
            unique[key] = row
    return list(unique.values())


def duplicate_key(row: dict[str, Any]) -> str:
    if row.get("osm_id"):
        return "osm|" + str(row["osm_id"])

    return "|".join(
        [
            normalize_text(row.get("location_type")),
            normalize_text(row.get("province")),
            normalize_text(row.get("name")),
            normalize_text(row.get("address")),
        ]
    )


def is_atm_candidate(row: dict[str, Any]) -> bool:
    location_type = row.get("location_type", "")
    return location_type in ATM_TYPES or "atm" in location_type


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def make_id(*values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
