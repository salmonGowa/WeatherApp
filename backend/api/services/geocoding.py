"""Place search via Photon OpenStreetMap data, keyless."""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache

from .http import get_json

CACHE_TTL = 60 * 60 * 24


def _label(props: dict) -> str:
    parts = [props.get("name")]
    for key in ("city", "state", "country"):
        value = props.get(key)
        if value and value not in parts:
            parts.append(value)
    return ", ".join(p for p in parts if p)


def search(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    key = (
        "geo:" + hashlib.sha1(f"{query.lower()}|{limit}".encode()).hexdigest()
    )
    cached = cache.get(key)
    if cached is not None:
        return cached

    data = get_json(
        "geocoding",
        settings.PHOTON_URL,
        {"q": query, "limit": limit, "lang": "en"},
    )
    results = []
    seen = set()
    for feature in data.get("features", []):
        lon, lat = feature["geometry"]["coordinates"]
        label = _label(feature.get("properties", {}))
        if not label or label in seen:
            continue
        seen.add(label)
        results.append({"label": label, "lat": lat, "lon": lon})

    cache.set(key, results, CACHE_TTL)
    return results
