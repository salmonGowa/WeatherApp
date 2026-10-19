"""
Trip planning: routes → checkpoints with ETAs → weather → risk →
recommendation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings

from . import geometry as geo
from . import hos, risk, routing, weather

ROUTE_IDS = "ABC"
SIMPLIFY_TOLERANCE_M = 25
HEATMAP_HOURS = 48


@dataclass(frozen=True)
class TripRequest:
    origin: geo.LatLon
    destination: geo.LatLon
    departure: datetime  # timezone-aware
    load_lb: float
    interval_miles: int
    apply_hos: bool = True


@dataclass
class Checkpoint:
    mile: float
    point: geo.LatLon
    elapsed_s: float
    covers: tuple[float, float] = (
        0.0,
        0.0,
    )  # miles of route this sample represents
    conditions: weather.Conditions | None = None
    assessment: risk.Assessment | None = None


@dataclass
class PlannedRoute:
    route: routing.Route
    cum_m: list[float]
    cum_drive_s: list[float]
    checkpoints: list[Checkpoint]
    stops: list[hos.Stop]

    @property
    def distance_miles(self) -> float:
        return self.cum_m[-1] / geo.METERS_PER_MILE

    @property
    def drive_s(self) -> float:
        return self.cum_drive_s[-1]

    @property
    def elapsed_s(self) -> float:
        return self.checkpoints[-1].elapsed_s


def truck_segment_durations(
    route: routing.Route, max_speed_mph: float
) -> list[float]:
    """Cap each segment's speed at a truck's typical maximum.

    OSRM's public server uses a car profile, so its ETAs would be
    optimistic for a truck on highways.
    """
    max_mps = max_speed_mph * geo.METERS_PER_MILE / 3600
    return [
        max(dur, dist / max_mps)
        for dist, dur in zip(
            route.seg_distance_m, route.seg_duration_s, strict=True
        )
    ]


def checkpoint_distances(total_m: float, interval_miles: float) -> list[float]:
    """0, N, 2N, … miles plus the destination."""
    step = interval_miles * geo.METERS_PER_MILE
    n = math.floor(total_m / step)
    dists = [k * step for k in range(n + 1)]
    if total_m - dists[-1] > 1e-6:
        dists.append(total_m)
    return dists


def build_route(route: routing.Route, req: TripRequest) -> PlannedRoute:
    cum_m = geo.cumulative(route.seg_distance_m)
    cum_drive = geo.cumulative(
        truck_segment_durations(route, settings.TRUCK_MAX_SPEED_MPH)
    )

    checkpoints = []
    for d in checkpoint_distances(cum_m[-1], req.interval_miles):
        drive_s = geo.interpolate(cum_m, cum_drive, d)
        checkpoints.append(
            Checkpoint(
                mile=d / geo.METERS_PER_MILE,
                point=geo.point_at_distance(route.coords, cum_m, d),
                elapsed_s=hos.elapsed_for_driving(drive_s, req.apply_hos),
            )
        )
    # Each checkpoint represents the stretch halfway to its neighbours,
    # so the covered miles add up exactly to the route length.
    for i, cp in enumerate(checkpoints):
        start = 0.0 if i == 0 else (checkpoints[i - 1].mile + cp.mile) / 2
        end = (
            cp.mile
            if i == len(checkpoints) - 1
            else (cp.mile + checkpoints[i + 1].mile) / 2
        )
        cp.covers = (start, end)

    return PlannedRoute(
        route=route,
        cum_m=cum_m,
        cum_drive_s=cum_drive,
        checkpoints=checkpoints,
        stops=hos.stops_for_trip(cum_drive[-1], req.apply_hos),
    )


def summarize(pr: PlannedRoute) -> risk.RouteRiskSummary:
    miles: dict[risk.RiskLevel, float] = dict.fromkeys(risk.RiskLevel, 0.0)
    for cp in pr.checkpoints:
        miles[cp.assessment.level] += cp.covers[1] - cp.covers[0]
    return risk.RouteRiskSummary(
        miles_by_level=miles,
        total_miles=pr.distance_miles,
        duration_hours=pr.elapsed_s / 3600,
    )


def _iso(dt: datetime) -> str:
    return (
        dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _risk_segments(pr: PlannedRoute) -> list[dict]:
    """Route geometry split into runs of equal risk level."""
    runs: list[tuple[risk.RiskLevel, float, float]] = []
    for cp in pr.checkpoints:
        lvl = cp.assessment.level
        if runs and runs[-1][0] == lvl:
            runs[-1] = (lvl, runs[-1][1], cp.covers[1])
        else:
            runs.append((lvl, cp.covers[0], cp.covers[1]))
    out = []
    for lvl, start, end in runs:
        piece = geo.slice_polyline(
            pr.route.coords,
            pr.cum_m,
            start * geo.METERS_PER_MILE,
            end * geo.METERS_PER_MILE,
        )
        out.append(
            {
                "level": lvl.key,
                "coords": [
                    [round(a, 5), round(b, 5)]
                    for a, b in geo.simplify(piece, SIMPLIFY_TOLERANCE_M)
                ],
            }
        )
    return out


def _stop_dict(pr: PlannedRoute, stop: hos.Stop, departure: datetime) -> dict:
    d = geo.interpolate(pr.cum_drive_s, pr.cum_m, stop.drive_s)
    lat, lon = geo.point_at_distance(pr.route.coords, pr.cum_m, d)
    start = departure + timedelta(seconds=stop.start_s)
    return {
        "kind": stop.kind,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "mile": round(d / geo.METERS_PER_MILE, 1),
        "start": _iso(start),
        "end": _iso(start + timedelta(seconds=stop.duration_s)),
    }


def _route_dict(
    rid: str,
    pr: PlannedRoute,
    summary: risk.RouteRiskSummary,
    req: TripRequest,
) -> dict:
    dep = req.departure
    return {
        "id": rid,
        "name": f"Route {rid}",
        "summary": pr.route.summary,
        "synthesized": pr.route.synthesized,
        "distance_miles": round(pr.distance_miles, 1),
        "drive_hours": round(pr.drive_s / 3600, 2),
        "duration_hours": round(pr.elapsed_s / 3600, 2),
        "departure": _iso(dep),
        "arrival": _iso(dep + timedelta(seconds=pr.elapsed_s)),
        "geometry": [
            [round(a, 5), round(b, 5)]
            for a, b in geo.simplify(pr.route.coords, SIMPLIFY_TOLERANCE_M)
        ],
        "segments": _risk_segments(pr),
        "stops": [_stop_dict(pr, s, dep) for s in pr.stops],
        "risk": summary.to_dict(),
        "checkpoints": [
            {
                "index": i,
                "mile": round(cp.mile, 1),
                "lat": round(cp.point[0], 5),
                "lon": round(cp.point[1], 5),
                "eta": _iso(dep + timedelta(seconds=cp.elapsed_s)),
                "covers": [round(cp.covers[0], 2), round(cp.covers[1], 2)],
                "weather": cp.conditions.to_dict(),
                "risk": cp.assessment.to_dict(),
            }
            for i, cp in enumerate(pr.checkpoints)
        ],
    }


def _recommendation(
    ids: list[str], summaries: list[risk.RouteRiskSummary]
) -> dict:
    order = risk.rank_routes(summaries)
    best = order[0]
    comparisons = []
    for other in order[1:]:
        why = risk.explain_choice(summaries[best], summaries[other])
        comparisons.append(
            {
                "route_id": ids[other],
                **(
                    why
                    or {
                        "criterion": "tie",
                        "phrase": "identical on every criterion",
                    }
                ),
            }
        )

    warning = None
    best_summary = summaries[best]
    if best_summary.miles(risk.RiskLevel.NO_TRAVEL) > 0:
        warning = (
            "Every route crosses No Travel conditions at the planned "
            "departure time. Consider delaying the trip."
        )
    elif best_summary.miles(risk.RiskLevel.SEVERE) > 0:
        warning = (
            "The safest route still includes Severe weather. "
            "Drive with extreme caution."
        )

    return {
        "route_id": ids[best],
        "ranking": [ids[i] for i in order],
        "comparisons": comparisons,
        "warning": warning,
    }


def plan_trip(req: TripRequest) -> dict:
    planned = [
        build_route(r, req)
        for r in routing.fetch_routes(req.origin, req.destination)
    ]

    all_cps = [cp for pr in planned for cp in pr.checkpoints]
    # Fetch at least the heatmap's 48h window so both requests share
    # cache entries.
    latest = req.departure + timedelta(
        seconds=max(HEATMAP_HOURS * 3600, max(pr.elapsed_s for pr in planned))
    )
    series = weather.fetch_hourly(
        [cp.point for cp in all_cps], req.departure, latest
    )
    for cp, s in zip(all_cps, series, strict=True):
        cp.conditions = s.at(req.departure.timestamp() + cp.elapsed_s)
        c = cp.conditions
        cp.assessment = risk.assess(
            c.wind_mph, c.rain_in_hr, c.snow_in_hr, req.load_lb
        )

    ids = list(ROUTE_IDS[: len(planned)])
    summaries = [summarize(pr) for pr in planned]
    recommendation = _recommendation(ids, summaries)
    routes = [
        _route_dict(rid, pr, s, req)
        for rid, pr, s in zip(ids, planned, summaries, strict=True)
    ]
    for r in routes:
        r["recommended"] = r["id"] == recommendation["route_id"]
        r["rank"] = recommendation["ranking"].index(r["id"]) + 1

    return {
        "departure": _iso(req.departure),
        "load_lb": req.load_lb,
        "interval_miles": req.interval_miles,
        "hos_applied": req.apply_hos,
        "truck_max_speed_mph": settings.TRUCK_MAX_SPEED_MPH,
        "routes": routes,
        "recommendation": recommendation,
    }
