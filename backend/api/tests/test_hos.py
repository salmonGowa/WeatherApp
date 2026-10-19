import pytest

from api.services.hos import elapsed_for_driving, stops_for_trip

H = 3600


@pytest.mark.parametrize(
    "drive_h, elapsed_h",
    [
        (0, 0),
        (5, 5),
        (8, 8),
        (9, 9.5),
        (11, 11.5),
        (12, 22.5),
        (22, 33),
        (23, 44),
    ],
)
def test_elapsed_for_driving(drive_h, elapsed_h):
    assert elapsed_for_driving(drive_h * H) == pytest.approx(elapsed_h * H)


def test_hos_disabled_is_identity():
    assert elapsed_for_driving(30 * H, enabled=False) == 30 * H
    assert stops_for_trip(30 * H, enabled=False) == []


def test_stops_for_trip():
    stops = stops_for_trip(20 * H)
    assert [(s.kind, s.drive_s / H, s.start_s / H) for s in stops] == [
        ("break", 8, 8),
        ("rest", 11, 11.5),
        ("break", 19, 29.5),
    ]
    assert stops_for_trip(8 * H) == []


def test_stops_consistent_with_elapsed():
    for stop in stops_for_trip(40 * H):
        assert elapsed_for_driving(stop.drive_s) == pytest.approx(stop.start_s)
