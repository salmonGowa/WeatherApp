"""
Route generation via OSRM.

OSRM's `alternatives=3` frequently returns fewer than three routes (it
only reports alternatives that pass its own quality filters). When that
happens we synthesise extra candidates by forcing the route through a
via point offset perpendicular to the origin→destination line, then keep
only candidates that are genuinely different and not absurdly slow.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache

from . import geometry as geo
from .http import ExternalServiceError, get_json

CACHE_TTL = 60 * 60 * 6
TARGET_ROUTES = 3
MAX_SHARED_FRACTION = 0.85
MAX_DURATION_RATIO = 1.5
VIA_OFFSETS = (0.15, -0.15, 0.3, -0.3)


@dataclass
class Route:
    coords: list[geo.LatLon]
    seg_distance_m: list[float]  # len(coords) - 1
    seg_duration_s: list[float]  # len(coords) - 1
    summary: str
    synthesized: bool = False
    _sample: list[geo.LatLon] = field(default_factory=list, repr=False)

    @property
    def distance_m(self) -> float:
        return sum(self.seg_distance_m)

    @property
    def duration_s(self) -> float:
        return sum(self.seg_duration_s)

    def sample(self) -> list[geo.LatLon]:
        if not self._sample:
            self._sample = geo.resample(self.coords, 2_000)
        return self._sample


def decode_polyline(encoded: str, precision: int = 6) -> list[geo.LatLon]:
    """Decode a Google encoded polyline (OSRM `polyline6`)."""
    coords: list[geo.LatLon] = []
    index = lat = lon = 0
    factor = 10**precision
    length = len(encoded)
    while index < length:
        for axis in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))
    return coords


def _summary(legs: list[dict]) -> str:
    names: list[str] = []
    for leg in legs:
        for part in (leg.get("summary") or "").split(","):
            part = part.strip()
            if part and part not in names:
                names.append(part)
    return ", ".join(names[:3])


def _parse_route(raw: dict, synthesized: bool = False) -> Route:
    coords = decode_polyline(raw["geometry"])
    dist: list[float] = []
    dur: list[float] = []
    for leg in raw["legs"]:
        dist.extend(leg["annotation"]["distance"])
        dur.extend(leg["annotation"]["duration"])
    n = min(len(coords) - 1, len(dist), len(dur))
    return Route(
        coords=coords[: n + 1],
        seg_distance_m=dist[:n],
        seg_duration_s=dur[:n],
        summary=_summary(raw["legs"]),
        synthesized=synthesized,
    )


def _osrm(waypoints: list[geo.LatLon], alternatives: bool) -> list[dict]:
    path = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)
    key = "osrm:" + hashlib.sha1(f"{path}|{alternatives}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    params = {
        "overview": "full",
        "geometries": "polyline6",
        "annotations": "distance,duration",
        "steps": "true",
        "alternatives": str(TARGET_ROUTES) if alternatives else "false",
    }
    if len(waypoints) > 2:
        params["continue_straight"] = "true"
    data = get_json(
        "routing", f"{settings.OSRM_URL}/route/v1/driving/{path}", params
    )
    if data.get("code") != "Ok":
        if data.get("code") in ("NoRoute", "NoSegment"):
            return []
        raise ExternalServiceError(
            "routing", data.get("message") or data.get("code", "error")
        )

    for r in data["routes"]:
        for leg in r["legs"]:
            leg.pop("steps", None)
    cache.set(key, data["routes"], CACHE_TTL)
    return data["routes"]


def shared_fraction(a: Route, b: Route, tolerance_m: float = 1_500) -> float:
    """Fraction of `a`'s length within `tolerance_m` of `b`."""
    cell = 0.02
    buckets: dict[tuple[int, int], list[geo.LatLon]] = {}
    for p in b.sample():
        buckets.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(
            p
        )

    pts = a.sample()
    near = 0
    for p in pts:
        ci, cj = int(p[0] // cell), int(p[1] // cell)
        if any(
            geo.haversine_m(p, q) <= tolerance_m
            for di in (-1, 0, 1)
            for dj in (-1, 0, 1)
            for q in buckets.get((ci + di, cj + dj), ())
        ):
            near += 1
    return near / len(pts)


def _is_distinct(candidate: Route, existing: list[Route]) -> bool:
    return all(
        shared_fraction(candidate, r) < MAX_SHARED_FRACTION for r in existing
    )


def _via_points(
    origin: geo.LatLon, destination: geo.LatLon
) -> list[geo.LatLon]:
    straight = geo.haversine_m(origin, destination)
    mid = ((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2)
    heading = geo.bearing_rad(origin, destination)
    return [
        geo.offset_point(mid, heading - math.pi / 2, f * straight)
        for f in VIA_OFFSETS
    ]


def fetch_routes(origin: geo.LatLon, destination: geo.LatLon) -> list[Route]:
    routes: list[Route] = []
    for raw in _osrm([origin, destination], alternatives=True):
        candidate = _parse_route(raw)
        if _is_distinct(candidate, routes):
            routes.append(candidate)
    if not routes:
        raise ExternalServiceError(
            "routing", "no drivable route found between these locations"
        )

    fastest = min(r.duration_s for r in routes)
    for via in _via_points(origin, destination):
        if len(routes) >= TARGET_ROUTES:
            break
        try:
            raws = _osrm([origin, via, destination], alternatives=False)
        except ExternalServiceError:
            continue
        if not raws:
            continue
        candidate = _parse_route(raws[0], synthesized=True)
        if candidate.duration_s > fastest * MAX_DURATION_RATIO:
            continue
        if _is_distinct(candidate, routes):
            routes.append(candidate)

    routes.sort(key=lambda r: r.duration_s)
    return routes[:TARGET_ROUTES]
