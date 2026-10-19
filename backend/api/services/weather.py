"""
Hourly forecasts from Open-Meteo keyless, multi-location requests.

"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.cache import cache

from . import geometry as geo
from .http import ExternalServiceError, get_json

CACHE_TTL = 60 * 30
BATCH_SIZE = 25
MAX_WORKERS = 4
GRID_DEG = 0.1
HOURLY_VARS = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
)
HOUR = 3600


@dataclass(frozen=True)
class Conditions:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float

    def to_dict(self) -> dict:
        return {
            "wind_mph": round(self.wind_mph, 1),
            "gust_mph": round(self.gust_mph, 1),
            "rain_in_hr": round(self.rain_in_hr, 3),
            "snow_in_hr": round(self.snow_in_hr, 3),
        }


@dataclass(frozen=True)
class HourlySeries:
    start: int
    wind: tuple[float, ...]
    gust: tuple[float, ...]
    rain: tuple[float, ...]
    snow: tuple[float, ...]

    def covers(self, ts: float) -> bool:
        return self.start <= ts <= self.start + (len(self.wind) - 1) * HOUR

    def _instant(self, values: tuple[float, ...], ts: float) -> float:
        pos = (ts - self.start) / HOUR
        i = max(0, min(len(values) - 1, math.floor(pos)))
        j = min(len(values) - 1, i + 1)
        t = max(0.0, min(1.0, pos - i))
        return values[i] + t * (values[j] - values[i])

    def _hour_ending(self, values: tuple[float, ...], ts: float) -> float:
        i = math.ceil((ts - self.start) / HOUR)
        return values[max(0, min(len(values) - 1, i))]

    def at(self, ts: float) -> Conditions:

        return Conditions(
            wind_mph=self._instant(self.wind, ts),
            gust_mph=self._instant(self.gust, ts),
            rain_in_hr=self._hour_ending(self.rain, ts),
            snow_in_hr=self._hour_ending(self.snow, ts),
        )

    def hour(self, i: int) -> Conditions:
        return Conditions(
            self.wind[i], self.gust[i], self.rain[i], self.snow[i]
        )


def snap(p: geo.LatLon) -> geo.LatLon:
    return (
        round(round(p[0] / GRID_DEG) * GRID_DEG, 4),
        round(round(p[1] / GRID_DEG) * GRID_DEG, 4),
    )


def _clean(values: list) -> tuple[float, ...]:
    return tuple(float(v) if v is not None else 0.0 for v in values)


def _parse(loc: dict) -> HourlySeries:
    h = loc["hourly"]
    rain = _clean(h["rain"])
    showers = _clean(h["showers"])
    return HourlySeries(
        start=int(h["time"][0]),
        wind=_clean(h["wind_speed_10m"]),
        gust=_clean(h["wind_gusts_10m"]),
        rain=tuple(r + s for r, s in zip(rain, showers, strict=True)),
        snow=_clean(h["snowfall"]),
    )


def _fetch_batch(
    points: list[geo.LatLon], start_date: str, end_date: str
) -> list[HourlySeries]:
    params = {
        "latitude": ",".join(f"{p[0]:.1f}" for p in points),
        "longitude": ",".join(f"{p[1]:.1f}" for p in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timeformat": "unixtime",
        "timezone": "GMT",
        "start_date": start_date,
        "end_date": end_date,
    }
    if settings.OPEN_METEO_API_KEY:
        params["apikey"] = settings.OPEN_METEO_API_KEY
    data = get_json(
        "weather",
        settings.OPEN_METEO_URL,
        params,
        timeout=settings.WEATHER_TIMEOUT_SECONDS,
    )
    locations = data if isinstance(data, list) else [data]
    if len(locations) != len(points):
        raise ExternalServiceError(
            "weather", "unexpected number of locations in response"
        )
    return [_parse(loc) for loc in locations]


def fetch_hourly(
    points: list[geo.LatLon], start: datetime, end: datetime
) -> list[HourlySeries]:
    """Hourly series covering [start, end] UTC for each point, in order.

    Requests are made for whole UTC days so overlapping plans share
    cache entries; points are de-duplicated after rounding.
    """
    start_date = start.astimezone(UTC).date().isoformat()
    end_date = (end.astimezone(UTC) + timedelta(hours=1)).date().isoformat()

    rounded = [snap(p) for p in points]
    unique = list(dict.fromkeys(rounded))
    keys = {p: f"wx:{p[0]}:{p[1]}:{start_date}:{end_date}" for p in unique}
    found: dict[geo.LatLon, HourlySeries] = {}
    cached = cache.get_many(list(keys.values()))
    for p, k in keys.items():
        if k in cached:
            found[p] = cached[k]

    missing = [p for p in unique if p not in found]
    batches = [
        missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)
    ]
    if batches:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            results = pool.map(
                lambda b: _fetch_batch(b, start_date, end_date), batches
            )
            fresh: dict[str, HourlySeries] = {}
            for batch, series in zip(batches, results, strict=True):
                for p, s in zip(batch, series, strict=True):
                    found[p] = s
                    fresh[keys[p]] = s
        cache.set_many(fresh, CACHE_TTL)

    return [found[p] for p in rounded]
