"""
Weather heatmap along the trip corridor.

The corridor is rasterised onto a regular grid in Web Mercator space, so
the frontend can render the grid as a single image overlay stretched
between its corner coordinates (Leaflet positions image overlays
linearly in Mercator). Only cells within 'corridor_miles' of a route are
included; each cell gets an hourly series for 'hours' + 1 frames.
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime, timedelta

from . import geometry as geo
from . import risk, weather

# Each cell is one Open-Meteo location (one API call against the free
# tier's per-IP limits), so the grid is kept small.
TARGET_CELLS = 150
MAX_CELLS = 250
MIN_CELL_M = 10_000  # finer than this exceeds the forecast models' resolution
MAX_CELL_M = 80_000
ROUTE_SAMPLE_M = 4_000


def _grid_for(
    samples: list[geo.LatLon], corridor_m: float, cell_m: float
) -> dict:
    lats = [p[0] for p in samples]
    mid_lat = (min(lats) + max(lats)) / 2
    pad_lat = max(abs(min(lats)), abs(max(lats)))
    pad = corridor_m * geo.mercator_units_per_meter(pad_lat)
    cell = cell_m * geo.mercator_units_per_meter(mid_lat)

    merc = [geo.to_mercator(p) for p in samples]
    border = pad + cell
    x0 = min(m[0] for m in merc) - border
    y0 = min(m[1] for m in merc) - border
    cols = max(3, math.ceil((max(m[0] for m in merc) + border - x0) / cell))
    rows = max(3, math.ceil((max(m[1] for m in merc) + border - y0) / cell))

    def center(r: int, c: int) -> geo.LatLon:
        return geo.from_mercator(x0 + (c + 0.5) * cell, y0 + (r + 0.5) * cell)

    reach = math.ceil(pad / cell) + 1
    limit = corridor_m + cell_m / 2
    mask: set[int] = set()
    for p, (mx, my) in zip(samples, merc, strict=True):
        pc, pr = int((mx - x0) / cell), int((my - y0) / cell)
        for r in range(max(1, pr - reach), min(rows - 1, pr + reach + 1)):
            for c in range(max(1, pc - reach), min(cols - 1, pc + reach + 1)):
                idx = r * cols + c
                if (
                    idx not in mask
                    and geo.haversine_m(p, center(r, c)) <= limit
                ):
                    mask.add(idx)

    north, west = geo.from_mercator(x0, y0)
    south, east = geo.from_mercator(x0 + cols * cell, y0 + rows * cell)
    cells = sorted(mask)
    return {
        "cols": cols,
        "rows": rows,
        "bounds": {"north": north, "south": south, "west": west, "east": east},
        "cells": cells,
        "centers": [center(i // cols, i % cols) for i in cells],
        "cell_km": cell_m / 1000,
    }


def build_grid(routes: list[list[geo.LatLon]], corridor_miles: float) -> dict:
    corridor_m = corridor_miles * geo.METERS_PER_MILE
    samples = [
        p for coords in routes for p in geo.resample(coords, ROUTE_SAMPLE_M)
    ]
    longest = max(
        sum(geo.haversine_m(a, b) for a, b in itertools.pairwise(c))
        for c in routes
    )
    area = 1.5 * longest * 2 * corridor_m + math.pi * corridor_m**2
    cell_m = min(MAX_CELL_M, max(MIN_CELL_M, math.sqrt(area / TARGET_CELLS)))

    grid = _grid_for(samples, corridor_m, cell_m)
    while len(grid["cells"]) > MAX_CELLS and cell_m < MAX_CELL_M:
        cell_m = min(
            MAX_CELL_M, cell_m * math.sqrt(len(grid["cells"]) / TARGET_CELLS)
        )
        grid = _grid_for(samples, corridor_m, cell_m)
    return grid


def build_heatmap(
    routes: list[list[geo.LatLon]],
    start: datetime,
    load_lb: float,
    hours: int = 48,
    corridor_miles: float = 40,
) -> dict:
    grid = build_grid(routes, corridor_miles)
    series = weather.fetch_hourly(
        grid.pop("centers"), start, start + timedelta(hours=hours)
    )
    start = start.replace(minute=0, second=0, microsecond=0)

    t0 = int(start.timestamp())
    wind, rain, snow, levels = [], [], [], []
    for s in series:
        offset = (t0 - s.start) // weather.HOUR
        w, r, sn, lv = [], [], [], []
        for h in range(hours + 1):
            c = s.hour(min(offset + h, len(s.wind) - 1))
            w.append(round(c.wind_mph, 1))
            r.append(round(c.rain_in_hr, 3))
            sn.append(round(c.snow_in_hr, 3))
            lv.append(
                int(
                    risk.assess(
                        c.wind_mph, c.rain_in_hr, c.snow_in_hr, load_lb
                    ).level
                )
            )
        wind.append(w)
        rain.append(r)
        snow.append(sn)
        levels.append(lv)

    return {
        "start": start.isoformat().replace("+00:00", "Z"),
        "hours": hours,
        "corridor_miles": corridor_miles,
        "grid": grid,
        "series": {"wind": wind, "rain": rain, "snow": snow, "risk": levels},
    }
