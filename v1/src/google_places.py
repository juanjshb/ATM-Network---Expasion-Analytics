from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import requests

from geo import infer_province_region


TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


class PlacesApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def search_text_places(
    *,
    api_key: str,
    query: str,
    field_mask: str,
    page_size: int = 20,
    max_pages: int = 3,
    delay_seconds: float = 2,
    timeout_seconds: float = 30,
) -> list[dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }

    places: list[dict[str, Any]] = []
    next_page_token: str | None = None
    safe_page_size = min(max(page_size, 1), 20)

    for page_number in range(1, max_pages + 1):
        payload: dict[str, Any] = {
            "textQuery": query,
            "pageSize": safe_page_size,
            "languageCode": "es",
            "regionCode": "DO",
        }
        if next_page_token:
            payload["pageToken"] = next_page_token

        try:
            response = requests.post(TEXT_SEARCH_URL, headers=headers, json=payload, timeout=timeout_seconds)
        except requests.RequestException as exc:
            raise PlacesApiError(f"Google Places API request failed: {exc}") from exc

        if response.status_code not in {200, 201}:
            raise PlacesApiError(
                f"Google Places API error {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        for place in data.get("places", []):
            places.append(normalize_place(place, query))

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        if page_number < max_pages:
            time.sleep(delay_seconds)

    return places


def normalize_place(place: dict[str, Any], query: str) -> dict[str, Any]:
    display_name = place.get("displayName", {})
    location = place.get("location", {})
    name = display_name.get("text") or "Unnamed ATM"
    address = place.get("formattedAddress") or ""
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    province, region = infer_province_region(name, address)

    fallback_key = "|".join([query, name, address, str(latitude), str(longitude)])
    google_place_id = place.get("id") or hashlib.sha1(fallback_key.encode("utf-8")).hexdigest()

    return {
        "google_place_id": google_place_id,
        "name": name,
        "address": address,
        "province": province,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "business_status": place.get("businessStatus"),
        "google_maps_uri": place.get("googleMapsUri"),
        "types": ",".join(place.get("types", [])),
        "raw_json": json.dumps(place, ensure_ascii=True),
    }
