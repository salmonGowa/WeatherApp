from datetime import UTC, datetime

import pytest

from api.services import geometry as geo
from api.services import heatmap

from .conftest import constant_series


def test_grid_covers_corridor_only():
    route = [(40.0, -105.0), (40.0, -95.0)]
    grid = heatmap.build_grid([route], corridor_miles=40)

    assert 0 < len(grid["cells"]) <= heatmap.MAX_CELLS
    assert len(grid["cells"]) < grid["cols"] * grid["rows"]
    cols, rows = grid["cols"], grid["rows"]
    for idx in grid["cells"]:
        r, c = divmod(idx, cols)
        assert 0 < r < rows - 1 and 0 < c < cols - 1
    b = grid["bounds"]
    assert b["north"] > 40.5 and b["south"] < 39.5
    assert b["west"] < -105 and b["east"] > -95

    limit = 40 * geo.METERS_PER_MILE + grid["cell_km"] * 1000 / 2
    route_pts = geo.resample(route, 4000)
    for c in grid["centers"]:
        assert min(geo.haversine_m(c, p) for p in route_pts) <= limit + 1


def test_mercator_roundtrip():
    for p in [(0.0, 0.0), (40.7, -74.0), (-33.9, 151.2), (64.1, -21.9)]:
        assert geo.from_mercator(*geo.to_mercator(p)) == pytest.approx(p)


def test_heatmap_frames_and_risk(monkeypatch):
    start = datetime(2026, 3, 1, 6, 30, tzinfo=UTC)
    day_start = int(datetime(2026, 3, 1, tzinfo=UTC).timestamp())
    monkeypatch.setattr(
        heatmap.weather,
        "fetch_hourly",
        lambda pts, s, e: [constant_series(day_start, wind=50) for _ in pts],
    )
    out = heatmap.build_heatmap(
        [[(40.0, -100.0), (40.0, -99.0)]], start, load_lb=35_000, hours=12
    )

    assert out["start"] == "2026-03-01T06:00:00Z"
    n = len(out["grid"]["cells"])
    assert "centers" not in out["grid"]
    for key in ("wind", "rain", "snow", "risk"):
        assert len(out["series"][key]) == n
        assert all(len(row) == 13 for row in out["series"][key])
    assert out["series"]["risk"][0][0] == 4
