"""Third-party API adapters, tested against mocked HTTP responses."""

import itertools
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from django.conf import settings

from api.services import routing, weather
from api.services.http import ExternalServiceError, get_json

H = 3600


def test_series_at_interpolates_wind_and_buckets_precip():
    s = weather.HourlySeries(
        start=0,
        wind=(10, 20, 30),
        gust=(15, 25, 35),
        rain=(0.0, 0.2, 0.4),
        snow=(0, 0, 1.0),
    )
    c = s.at(1.5 * H)
    assert c.wind_mph == pytest.approx(25)
    assert c.rain_in_hr == 0.4
    assert c.snow_in_hr == 1.0
    assert s.at(1 * H).rain_in_hr == 0.2


def open_meteo_payload(n, hours=72):
    loc = {
        "hourly": {
            "time": [1_700_000_000 + i * H for i in range(hours)],
            "wind_speed_10m": [12.0] * hours,
            "wind_gusts_10m": [20.0] * hours,
            "rain": [0.05] * hours,
            "showers": [0.10] * hours,
            "snowfall": [None] * hours,
        }
    }
    return loc if n == 1 else [loc] * n


@respx.mock
def test_fetch_hourly_snaps_dedupes_and_caches():
    route = respx.get(settings.OPEN_METEO_URL).mock(
        side_effect=lambda req: httpx.Response(
            200,
            json=open_meteo_payload(
                len(
                    parse_qs(urlparse(str(req.url)).query)["latitude"][
                        0
                    ].split(",")
                )
            ),
        )
    )
    start = datetime(2026, 1, 1, 10, tzinfo=UTC)
    end = datetime(2026, 1, 2, 10, tzinfo=UTC)
    points = [(40.01, -100.02), (39.99, -99.98), (41.0, -101.0)]

    series = weather.fetch_hourly(points, start, end)
    assert len(series) == 3
    assert series[0] is series[1]
    assert series[0].rain[0] == pytest.approx(0.15)
    assert series[0].snow[0] == 0.0

    query = parse_qs(urlparse(str(route.calls[0].request.url)).query)
    assert query["latitude"] == ["40.0,41.0"]
    assert query["wind_speed_unit"] == ["mph"]
    assert query["precipitation_unit"] == ["inch"]

    weather.fetch_hourly(points, start, end)
    assert route.call_count == 1


@respx.mock
def test_weather_retries_then_reports_rate_limit(monkeypatch):
    monkeypatch.setattr("api.services.http.time.sleep", lambda s: None)
    route = respx.get(settings.OPEN_METEO_URL).mock(
        return_value=httpx.Response(429)
    )
    with pytest.raises(ExternalServiceError, match="rate limited"):
        weather.fetch_hourly(
            [(40, -100)],
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, 5, tzinfo=UTC),
        )
    assert route.call_count == 4


def encode_polyline(coords, precision=6):
    factor = 10**precision
    out, prev = [], (0, 0)
    for lat, lon in coords:
        cur = (round(lat * factor), round(lon * factor))
        for delta in (cur[0] - prev[0], cur[1] - prev[1]):
            v = ~(delta << 1) if delta < 0 else delta << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        prev = cur
    return "".join(out)


def test_decode_polyline_reference_vector():
    coords = routing.decode_polyline(
        "_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision=5
    )
    assert coords == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def osrm_route(coords, mph=60, summary="I 80"):
    n = len(coords) - 1
    from api.services import geometry as geo

    dist = [geo.haversine_m(a, b) for a, b in itertools.pairwise(coords)]
    dur = [d / (mph * 0.44704) for d in dist]
    return {
        "geometry": encode_polyline(coords),
        "legs": [
            {
                "summary": summary,
                "annotation": {"distance": dist[:n], "duration": dur[:n]},
            }
        ],
    }


def line(a, b, steps=100):
    return [
        (a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps)
        for k in range(steps + 1)
    ]


@respx.mock
def test_fetch_routes_synthesizes_missing_alternatives():
    origin, dest = (40.0, -100.0), (40.0, -96.0)
    direct = line(origin, dest)
    north = line(origin, (41.0, -98.0), 50) + line((41.0, -98.0), dest, 50)[1:]
    south = line(origin, (39.0, -98.0), 50) + line((39.0, -98.0), dest, 50)[1:]
    via_responses = iter([north, direct, south])

    def handler(request):
        path = request.url.path
        if path.count(";") == 1:
            return httpx.Response(
                200, json={"code": "Ok", "routes": [osrm_route(direct)]}
            )
        return httpx.Response(
            200,
            json={
                "code": "Ok",
                "routes": [osrm_route(next(via_responses), summary="US 6")],
            },
        )

    respx.get(url__startswith=settings.OSRM_URL).mock(side_effect=handler)

    routes = routing.fetch_routes(origin, dest)
    assert len(routes) == 3
    assert routes[0].synthesized is False
    assert all(r.synthesized for r in routes[1:])
    assert routes[0].duration_s <= routes[1].duration_s <= routes[2].duration_s


@respx.mock
def test_fetch_routes_no_route():
    respx.get(url__startswith=settings.OSRM_URL).mock(
        return_value=httpx.Response(
            200, json={"code": "NoRoute", "routes": []}
        )
    )
    with pytest.raises(ExternalServiceError, match="no drivable route"):
        routing.fetch_routes((40, -100), (21.3, -157.8))


@respx.mock
def test_retry_recovers_after_transient_error(monkeypatch):
    sleeps = []
    monkeypatch.setattr("api.services.http.time.sleep", sleeps.append)
    respx.get("https://example.test/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": 1})]
    )
    assert get_json("svc", "https://example.test/x") == {"ok": 1}
    assert sleeps == [1.0]
