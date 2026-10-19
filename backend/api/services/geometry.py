"""Small geodesic helpers; coordinates are (lat, lon) in degrees."""

from __future__ import annotations

import itertools
import math
from bisect import bisect_right

EARTH_RADIUS_M = 6_371_008.8
METERS_PER_MILE = 1609.344
MERCATOR_MAX_LAT = 85.05112878

LatLon = tuple[float, float]


def haversine_m(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def cumulative(values: list[float]) -> list[float]:
    """[a, b, c] -> [0, a, a+b, a+b+c]"""
    out = [0.0]
    for v in values:
        out.append(out[-1] + v)
    return out


def interpolate(xs: list[float], ys: list[float], x: float) -> float:
    """Piecewise-linear interpolation; xs must be ascending."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_right(xs, x) - 1
    span = xs[i + 1] - xs[i]
    t = 0.0 if span == 0 else (x - xs[i]) / span
    return ys[i] + t * (ys[i + 1] - ys[i])


def point_at_distance(
    coords: list[LatLon], cum_m: list[float], d: float
) -> LatLon:
    """Position along the polyline 'd' meters from its start."""
    if d <= 0:
        return coords[0]
    if d >= cum_m[-1]:
        return coords[-1]
    i = bisect_right(cum_m, d) - 1
    span = cum_m[i + 1] - cum_m[i]
    t = 0.0 if span == 0 else (d - cum_m[i]) / span
    (lat1, lon1), (lat2, lon2) = coords[i], coords[i + 1]
    return (lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1))


def resample(coords: list[LatLon], step_m: float) -> list[LatLon]:
    """Points every 'step_m' along the polyline, always including both
    ends.
    """
    cum = cumulative(
        [haversine_m(a, b) for a, b in itertools.pairwise(coords)]
    )
    total = cum[-1]
    n = max(1, math.ceil(total / step_m))
    return [
        point_at_distance(coords, cum, total * k / n) for k in range(n + 1)
    ]


def offset_point(
    origin: LatLon, bearing_rad: float, distance_m: float
) -> LatLon:
    """Point reached from 'origin' along a bearing."""
    lat1, lon1 = map(math.radians, origin)
    ang = distance_m / EARTH_RADIUS_M
    lat2 = math.asin(
        math.sin(lat1) * math.cos(ang)
        + math.cos(lat1) * math.sin(ang) * math.cos(bearing_rad)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing_rad) * math.sin(ang) * math.cos(lat1),
        math.cos(ang) - math.sin(lat1) * math.sin(lat2),
    )
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def bearing_rad(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
        lat2
    ) * math.cos(dlon)
    return math.atan2(y, x)


def to_mercator(p: LatLon) -> tuple[float, float]:
    lat = max(-MERCATOR_MAX_LAT, min(MERCATOR_MAX_LAT, p[0]))
    x = (p[1] + 180.0) / 360.0
    s = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    return x, y


def from_mercator(x: float, y: float) -> LatLon:
    lon = x * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y))))
    return lat, lon


def mercator_units_per_meter(lat: float) -> float:
    """Scale factor of the unit Mercator plane at a latitude."""
    return 1.0 / (2 * math.pi * EARTH_RADIUS_M * math.cos(math.radians(lat)))


def simplify(coords: list[LatLon], tolerance_m: float) -> list[LatLon]:

    if len(coords) < 3:
        return list(coords)
    lat0 = math.radians(sum(c[0] for c in coords) / len(coords))
    kx = math.cos(lat0) * EARTH_RADIUS_M * math.pi / 180
    ky = EARTH_RADIUS_M * math.pi / 180
    pts = [(c[1] * kx, c[0] * ky) for c in coords]

    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    tol2 = tolerance_m * tolerance_m
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = pts[i], pts[j]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        worst, worst_d2 = -1, tol2
        for k in range(i + 1, j):
            px, py = pts[k]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(
                    0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2)
                )
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > worst_d2:
                worst, worst_d2 = k, d2
        if worst != -1:
            keep[worst] = True
            stack.extend(((i, worst), (worst, j)))
    return [c for c, k in zip(coords, keep, strict=True) if k]


def slice_polyline(
    coords: list[LatLon], cum_m: list[float], start: float, end: float
) -> list[LatLon]:
    """Sub-polyline between two distances along the line, inclusive."""
    lo = bisect_right(cum_m, start)
    hi = bisect_right(cum_m, end)
    middle = coords[lo:hi]
    return [
        point_at_distance(coords, cum_m, start),
        *middle,
        point_at_distance(coords, cum_m, end),
    ]
