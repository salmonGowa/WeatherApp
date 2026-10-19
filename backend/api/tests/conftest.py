import itertools
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from api.services import geometry as geo
from api.services.routing import Route
from api.services.weather import HourlySeries


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def departure():
    return (datetime.now(UTC) + timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0
    )


def straight_route(start, end, mph=60.0, steps=200, summary="Test Hwy"):
    """A route along a straight line driven at a constant speed."""
    coords = [
        (
            start[0] + (end[0] - start[0]) * k / steps,
            start[1] + (end[1] - start[1]) * k / steps,
        )
        for k in range(steps + 1)
    ]
    dist = [geo.haversine_m(a, b) for a, b in itertools.pairwise(coords)]
    mps = mph * geo.METERS_PER_MILE / 3600
    return Route(
        coords=coords,
        seg_distance_m=dist,
        seg_duration_s=[d / mps for d in dist],
        summary=summary,
    )


def constant_series(start_ts, hours=24 * 20, wind=5.0, rain=0.0, snow=0.0):
    n = hours + 1
    return HourlySeries(
        start=start_ts,
        wind=(wind,) * n,
        gust=(wind,) * n,
        rain=(rain,) * n,
        snow=(snow,) * n,
    )
