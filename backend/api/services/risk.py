"""
Weather risk classification and route recommendation.

Pure functions only (no I/O) so the rules can be unit tested exactly
Threshold interpretation:
Wind ("<25", "25–34", "35–44", "45–54", "=>55"): the bands are integer
mph, so fractional values are banded by their lower edge: 34.9 mph is
Moderate, 35.0 mph is High.

Rain / snow ("<0.10", "0.10–0.25", ..., ">1.00")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def key(self) -> str:
        return self.name.lower()


_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}

# Lower bounds (inclusive) for Moderate, High, Severe, No Travel.
WIND_LOWER_BOUNDS_MPH = (25.0, 35.0, 45.0, 55.0)
# Upper bounds (inclusive) for Low is exclusive "<0.10"; for the rest
# inclusive.
RAIN_UPPER_BOUNDS_IN_HR = (0.10, 0.25, 0.50, 1.00)
SNOW_UPPER_BOUNDS_IN_HR = (0.5, 1.0, 2.0, 3.0)

# Load rules
HEAVY_LOAD_NO_TRAVEL_LB = 30_000  # 45–54 mph + > 30,000 lb -> No Travel
HEAVY_LOAD_SEVERE_LB = 40_000  # 35–44 mph + > 40,000 lb -> Severe


def classify_wind(mph: float) -> RiskLevel:
    level = RiskLevel.LOW
    for i, bound in enumerate(WIND_LOWER_BOUNDS_MPH, start=1):
        if mph >= bound:
            level = RiskLevel(i)
    return level


def _classify_precip(rate: float, bounds: tuple[float, ...]) -> RiskLevel:
    low_upper, mod_upper, high_upper, severe_upper = bounds
    if rate < low_upper:
        return RiskLevel.LOW
    if rate <= mod_upper:
        return RiskLevel.MODERATE
    if rate <= high_upper:
        return RiskLevel.HIGH
    if rate <= severe_upper:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(in_per_hr: float) -> RiskLevel:
    return _classify_precip(in_per_hr, RAIN_UPPER_BOUNDS_IN_HR)


def classify_snow(in_per_hr: float) -> RiskLevel:
    return _classify_precip(in_per_hr, SNOW_UPPER_BOUNDS_IN_HR)


def apply_load_rules(wind_level: RiskLevel, load_lb: float) -> RiskLevel:
    """Escalate the wind level for heavy loads.

    The >=55 mph rule needs no load check: the base wind table already
    makes it No Travel.
    """
    if wind_level == RiskLevel.SEVERE and load_lb > HEAVY_LOAD_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if wind_level == RiskLevel.HIGH and load_lb > HEAVY_LOAD_SEVERE_LB:
        return RiskLevel.SEVERE
    return wind_level


@dataclass(frozen=True)
class Factor:
    condition: str  # "wind" | "rain" | "snow"
    value: float
    unit: str
    level: RiskLevel
    load_adjusted: bool = False

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "value": round(self.value, 2),
            "unit": self.unit,
            "level": self.level.key,
            "load_adjusted": self.load_adjusted,
        }


@dataclass(frozen=True)
class Assessment:
    level: RiskLevel
    factors: tuple[Factor, ...]

    @property
    def drivers(self) -> list[str]:
        """Conditions that set the overall level (empty when Low)."""
        if self.level == RiskLevel.LOW:
            return []
        return [f.condition for f in self.factors if f.level == self.level]

    def to_dict(self) -> dict:
        return {
            "level": self.level.key,
            "score": int(self.level),
            "drivers": self.drivers,
            "factors": [f.to_dict() for f in self.factors],
        }


def assess(
    wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float
) -> Assessment:
    """Overall risk is the worst of the individual conditions."""
    base_wind = classify_wind(wind_mph)
    wind = apply_load_rules(base_wind, load_lb)
    factors = (
        Factor("wind", wind_mph, "mph", wind, load_adjusted=wind != base_wind),
        Factor("rain", rain_in_hr, "in/hr", classify_rain(rain_in_hr)),
        Factor("snow", snow_in_hr, "in/hr", classify_snow(snow_in_hr)),
    )
    return Assessment(max(f.level for f in factors), factors)


# Route-level aggregation and recommendation


@dataclass(frozen=True)
class RouteRiskSummary:
    miles_by_level: dict[RiskLevel, float]
    total_miles: float
    duration_hours: float

    @property
    def average_risk(self) -> float:
        """Distance-weighted mean risk (0 = Low … 4 = No Travel)."""
        if self.total_miles <= 0:
            return 0.0
        weighted = sum(
            int(level) * miles for level, miles in self.miles_by_level.items()
        )
        return weighted / self.total_miles

    @property
    def max_level(self) -> RiskLevel:
        present = [
            lvl for lvl, miles in self.miles_by_level.items() if miles > 0
        ]
        return max(present) if present else RiskLevel.LOW

    def miles(self, level: RiskLevel) -> float:
        return self.miles_by_level.get(level, 0.0)

    def ranking_key(self) -> tuple:

        return (
            round(self.miles(RiskLevel.NO_TRAVEL), 1),
            round(self.miles(RiskLevel.SEVERE), 1),
            round(self.miles(RiskLevel.HIGH), 1),
            round(self.average_risk, 2),
            round(self.duration_hours, 2),
        )

    def to_dict(self) -> dict:
        return {
            "miles_by_level": {
                lvl.key: round(self.miles(lvl), 1) for lvl in RiskLevel
            },
            "total_miles": round(self.total_miles, 1),
            "average_risk": round(self.average_risk, 2),
            "max_level": self.max_level.key,
        }


CRITERIA = (
    ("no_travel_miles", "fewer No Travel miles"),
    ("severe_miles", "fewer Severe miles"),
    ("high_miles", "fewer High miles"),
    ("average_risk", "lower average risk"),
    ("duration_hours", "shorter travel time"),
)


def rank_routes(summaries: list[RouteRiskSummary]) -> list[int]:
    """Route indices ordered best-first (stable for exact ties)."""
    return sorted(
        range(len(summaries)), key=lambda i: summaries[i].ranking_key()
    )


def explain_choice(
    best: RouteRiskSummary, other: RouteRiskSummary
) -> dict | None:
    """Find the first criterion that separates `best` from `other`."""
    for (name, phrase), a, b in zip(
        CRITERIA, best.ranking_key(), other.ranking_key(), strict=True
    ):
        if a != b:
            return {"criterion": name, "phrase": phrase, "best": a, "other": b}
    return None
