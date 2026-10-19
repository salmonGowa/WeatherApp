import pytest

from api.services.risk import (
    RiskLevel,
    RouteRiskSummary,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
    explain_choice,
    rank_routes,
)

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, L),
        (24.9, L),
        (25, M),
        (34, M),
        (34.9, M),
        (35, H),
        (44, H),
        (45, S),
        (54.9, S),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_bands(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [
        (0, L),
        (0.09, L),
        (0.10, M),
        (0.25, M),
        (0.26, H),
        (0.50, H),
        (0.51, S),
        (1.00, S),
        (1.01, NT),
    ],
)
def test_rain_bands(rate, expected):
    assert classify_rain(rate) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [
        (0, L),
        (0.49, L),
        (0.5, M),
        (1.0, M),
        (1.1, H),
        (2.0, H),
        (2.5, S),
        (3.0, S),
        (3.01, NT),
    ],
)
def test_snow_bands(rate, expected):
    assert classify_snow(rate) == expected


@pytest.mark.parametrize(
    "mph, load, expected",
    [
        (55, 0, NT),
        (50, 30_000, S),
        (50, 30_001, NT),
        (40, 40_000, H),
        (40, 40_001, S),
        (30, 80_000, M),
    ],
)
def test_load_rules(mph, load, expected):
    result = assess(mph, 0, 0, load)
    assert result.level == expected
    wind = result.factors[0]
    assert wind.load_adjusted == (classify_wind(mph) != expected)


def test_overall_level_is_worst_factor_and_reports_drivers():
    result = assess(
        wind_mph=30, rain_in_hr=0.6, snow_in_hr=0.0, load_lb=10_000
    )
    assert result.level == S
    assert result.drivers == ["rain"]
    assert assess(5, 0, 0, 0).drivers == []


def summary(
    no_travel=0.0, severe=0.0, high=0.0, moderate=0.0, low=100.0, hours=10.0
):
    miles = {NT: no_travel, S: severe, H: high, M: moderate, L: low}
    return RouteRiskSummary(miles, sum(miles.values()), hours)


def test_average_risk_is_distance_weighted():
    s = summary(high=25, low=75)
    assert s.average_risk == pytest.approx(0.5)
    assert s.max_level == H


def test_ranking_follows_spec_priority():
    routes = [
        summary(severe=5, hours=5),
        summary(high=50, hours=9),
        summary(high=10, moderate=80, hours=12),
    ]
    assert rank_routes(routes) == [2, 1, 0]


def test_average_risk_breaks_tie_before_travel_time():
    calm = summary(moderate=10, hours=12)
    breezy = summary(moderate=40, hours=8)
    assert rank_routes([breezy, calm]) == [1, 0]
    assert explain_choice(calm, breezy)["criterion"] == "average_risk"


def test_travel_time_is_last_resort():
    assert rank_routes([summary(hours=11), summary(hours=10)]) == [1, 0]


def test_no_travel_miles_outrank_everything():
    blocked = summary(no_travel=1, hours=3)
    severe = summary(severe=40, hours=20)
    assert rank_routes([blocked, severe]) == [1, 0]
    assert explain_choice(severe, blocked)["criterion"] == "no_travel_miles"


def test_float_noise_does_not_decide():
    a = summary(severe=10.01, hours=9)
    b = summary(severe=10.02, hours=8)
    assert rank_routes([a, b]) == [1, 0]
