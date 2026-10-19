import itertools

import pytest
from django.test import override_settings

from api.services import geometry as geo
from api.services import planner

from .conftest import constant_series, straight_route


def make_request(departure, **overrides):
    params = {
        "origin": (40.0, -100.0),
        "destination": (40.0, -98.0),
        "departure": departure,
        "load_lb": 20_000,
        "interval_miles": 25,
        "apply_hos": False,
        **overrides,
    }
    return planner.TripRequest(**params)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_checkpoint_distances(interval):
    total = 107.3 * geo.METERS_PER_MILE
    miles = [
        d / geo.METERS_PER_MILE
        for d in planner.checkpoint_distances(total, interval)
    ]
    assert miles[0] == 0
    assert miles[-1] == pytest.approx(107.3)
    assert all(b - a <= interval + 1e-9 for a, b in itertools.pairwise(miles))
    assert miles[1] == pytest.approx(interval)


@override_settings(TRUCK_MAX_SPEED_MPH=65)
def test_build_route_etas_and_coverage(departure):
    route = straight_route((40.0, -100.0), (40.0, -98.0), mph=50)
    pr = planner.build_route(route, make_request(departure))

    for cp in pr.checkpoints:
        assert cp.elapsed_s == pytest.approx(cp.mile / 50 * 3600, rel=1e-6)
    assert pr.checkpoints[0].covers[0] == 0
    assert pr.checkpoints[-1].covers[1] == pytest.approx(pr.distance_miles)
    for a, b in itertools.pairwise(pr.checkpoints):
        assert a.covers[1] == pytest.approx(b.covers[0])


@override_settings(TRUCK_MAX_SPEED_MPH=65)
def test_truck_speed_cap_slows_fast_segments(departure):
    route = straight_route((40.0, -100.0), (40.0, -98.0), mph=80)
    pr = planner.build_route(route, make_request(departure))
    assert pr.drive_s == pytest.approx(pr.distance_miles / 65 * 3600, rel=1e-6)


def test_hos_applies_to_long_trips(departure):
    route = straight_route((40.0, -110.0), (40.0, -98.0), mph=60)
    with_hos = planner.build_route(
        route, make_request(departure, apply_hos=True)
    )
    without = planner.build_route(
        route, make_request(departure, apply_hos=False)
    )
    assert with_hos.elapsed_s - without.elapsed_s == pytest.approx(1800)
    assert [s.kind for s in with_hos.stops] == ["break"]


def test_plan_prefers_safer_route_over_faster(monkeypatch, departure):
    fast = straight_route(
        (40.0, -100.0), (40.0, -98.0), mph=60, summary="Fast"
    )
    slow = straight_route(
        (40.0, -100.0), (40.5, -98.0), mph=45, summary="Slow"
    )
    monkeypatch.setattr(
        planner.routing, "fetch_routes", lambda o, d: [fast, slow]
    )

    def stormy(p):
        """40 mph winds mid-way along the fast (lat 40.0) corridor."""
        return abs(p[0] - 40.0) < 0.01 and -99.5 < p[1] < -98.5

    def fake_weather(points, start, end):
        t0 = int(start.timestamp()) - 3600
        return [
            constant_series(t0, wind=40.0 if stormy(p) else 5.0)
            for p in points
        ]

    monkeypatch.setattr(planner.weather, "fetch_hourly", fake_weather)

    result = planner.plan_trip(make_request(departure, load_lb=45_000))
    routes = {r["summary"]: r for r in result["routes"]}

    assert routes["Fast"]["risk"]["miles_by_level"]["severe"] > 0
    assert routes["Slow"]["recommended"] is True
    assert (
        result["recommendation"]["comparisons"][0]["criterion"]
        == "severe_miles"
    )
    assert result["recommendation"]["warning"] is None

    cp = routes["Fast"]["checkpoints"][2]
    assert cp["risk"]["level"] == "severe"
    assert cp["risk"]["factors"][0]["load_adjusted"] is True

    light = planner.plan_trip(make_request(departure, load_lb=10_000))
    assert (
        light["recommendation"]["comparisons"][0]["criterion"] == "high_miles"
    )


def test_plan_warns_when_every_route_is_no_travel(monkeypatch, departure):
    route = straight_route((40.0, -100.0), (40.0, -98.0))
    monkeypatch.setattr(planner.routing, "fetch_routes", lambda o, d: [route])
    monkeypatch.setattr(
        planner.weather,
        "fetch_hourly",
        lambda pts, s, e: [
            constant_series(int(s.timestamp()) - 3600, wind=60) for _ in pts
        ],
    )
    result = planner.plan_trip(make_request(departure))
    assert result["routes"][0]["risk"]["max_level"] == "no_travel"
    assert "No Travel" in result["recommendation"]["warning"]


def test_risk_segments_merge_equal_levels(monkeypatch, departure):
    route = straight_route((40.0, -100.0), (40.0, -98.0))
    monkeypatch.setattr(planner.routing, "fetch_routes", lambda o, d: [route])
    monkeypatch.setattr(
        planner.weather,
        "fetch_hourly",
        lambda pts, s, e: [
            constant_series(
                int(s.timestamp()) - 3600, wind=30 if p[1] > -99 else 5
            )
            for p in pts
        ],
    )
    segments = planner.plan_trip(make_request(departure, interval_miles=10))[
        "routes"
    ][0]["segments"]
    assert [s["level"] for s in segments] == ["low", "moderate"]
