from datetime import UTC, datetime, timedelta

import pytest
from rest_framework.test import APIClient

from api.controllers import geocode_controller, plan_controller
from api.services.http import ExternalServiceError


@pytest.fixture
def client():
    return APIClient()


def plan_body(**overrides):
    body = {
        "origin": {"lat": 41.88, "lon": -87.63, "label": "Chicago"},
        "destination": {"lat": 39.74, "lon": -104.99, "label": "Denver"},
        "departure": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        "load_lb": 35000,
        "interval_miles": 25,
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"interval_miles": 15}, "interval_miles"),
        ({"load_lb": -1}, "load_lb"),
        (
            {
                "departure": (
                    datetime.now(UTC) + timedelta(days=30)
                ).isoformat()
            },
            "departure",
        ),
        ({"origin": {"lat": 95, "lon": 0}}, "origin"),
    ],
)
def test_plan_validation(client, overrides, field):
    resp = client.post("/api/plan/", plan_body(**overrides), format="json")
    assert resp.status_code == 400
    assert field in resp.json()


def test_plan_rejects_identical_endpoints(client):
    same = {"lat": 41.88, "lon": -87.63}
    resp = client.post(
        "/api/plan/", plan_body(origin=same, destination=same), format="json"
    )
    assert resp.status_code == 400


def test_plan_passes_request_to_planner(client, monkeypatch):
    captured = {}

    def fake_plan(trip):
        captured["trip"] = trip
        return {"routes": []}

    monkeypatch.setattr(plan_controller.planner, "plan_trip", fake_plan)
    resp = client.post("/api/plan/", plan_body(apply_hos=False), format="json")
    assert resp.status_code == 200
    trip = captured["trip"]
    assert trip.origin == (41.88, -87.63)
    assert trip.interval_miles == 25
    assert trip.apply_hos is False
    assert trip.departure.tzinfo is not None


def test_upstream_failure_returns_502(client, monkeypatch):
    def boom(trip):
        raise ExternalServiceError("weather", "timed out")

    monkeypatch.setattr(plan_controller.planner, "plan_trip", boom)
    resp = client.post("/api/plan/", plan_body(), format="json")
    assert resp.status_code == 502
    assert resp.json()["service"] == "weather"


def test_geocode_requires_query(client):
    assert client.get("/api/geocode/").status_code == 400


def test_geocode(client, monkeypatch):
    monkeypatch.setattr(
        geocode_controller.geocoding,
        "search",
        lambda q: [{"label": q, "lat": 1, "lon": 2}],
    )
    resp = client.get("/api/geocode/", {"q": "Denver"})
    assert resp.json() == {
        "results": [{"label": "Denver", "lat": 1, "lon": 2}]
    }


def test_heatmap_validation(client):
    resp = client.post(
        "/api/heatmap/",
        {
            "routes": [[[40, -100]]],
            "start": datetime.now(UTC).isoformat(),
            "load_lb": 1000,
        },
        format="json",
    )
    assert resp.status_code == 400


def test_health(client):
    assert client.get("/api/health/").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/api/plan/"),
        ("get", "/api/heatmap/"),
        ("post", "/api/geocode/"),
    ],
)
def test_unsupported_methods_return_405(client, method, url):
    assert getattr(client, method)(url).status_code == 405


def test_base_controller_rejects_unimplemented_actions():
    from rest_framework.exceptions import MethodNotAllowed
    from rest_framework.test import APIRequestFactory

    from api.controllers import HealthController

    request = APIRequestFactory().delete("/api/health/1/")
    with pytest.raises(MethodNotAllowed):
        HealthController().destroy(request, pk=1)
