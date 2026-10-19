"""
Simplified FMCSA hours-of-service model (property-carrying drivers) used
to turn driving time into wall-clock time:

* a 30-minute break is required after 8 cumulative hours of driving;
* at most 11 hours of driving, then 10 consecutive hours off duty.

8h drive + 0.5h break + 3h drive = 11.5h on duty, inside the 14-hour
window, so the 14-hour rule never binds under this schedule. The
60/70-hour weekly limit is ignored (trips are short relative to it).
"""

from __future__ import annotations

from dataclasses import dataclass

HOUR = 3600.0
BREAK_AFTER_DRIVING = 8 * HOUR
BREAK_LENGTH = 0.5 * HOUR
MAX_DRIVING_PER_SHIFT = 11 * HOUR
REST_LENGTH = 10 * HOUR
SHIFT_ELAPSED = MAX_DRIVING_PER_SHIFT + BREAK_LENGTH  # 11.5h
CYCLE_ELAPSED = SHIFT_ELAPSED + REST_LENGTH  # 21.5h


def elapsed_for_driving(drive_s: float, enabled: bool = True) -> float:
    """Wall-clock seconds from departure until 'drive_s' of driving is
    done.

    A stop that starts exactly when the driving ends is not counted (the
    truck has arrived).
    """
    if not enabled or drive_s <= 0:
        return max(0.0, drive_s)
    full_shifts, remainder = divmod(drive_s, MAX_DRIVING_PER_SHIFT)
    if remainder == 0:
        full_shifts -= 1
        remainder = MAX_DRIVING_PER_SHIFT
    within = (
        remainder
        if remainder <= BREAK_AFTER_DRIVING
        else remainder + BREAK_LENGTH
    )
    return full_shifts * CYCLE_ELAPSED + within


@dataclass(frozen=True)
class Stop:
    kind: str  # "break" | "rest"
    drive_s: float  # driving completed when the stop starts
    start_s: float  # elapsed wall-clock seconds at stop start
    duration_s: float


def stops_for_trip(total_drive_s: float, enabled: bool = True) -> list[Stop]:
    """Mandatory stops strictly before arrival."""
    if not enabled:
        return []
    stops: list[Stop] = []
    shift = 0
    while True:
        base_drive = shift * MAX_DRIVING_PER_SHIFT
        base_elapsed = shift * CYCLE_ELAPSED
        brk = base_drive + BREAK_AFTER_DRIVING
        if brk >= total_drive_s:
            break
        stops.append(
            Stop(
                "break", brk, base_elapsed + BREAK_AFTER_DRIVING, BREAK_LENGTH
            )
        )
        rest = base_drive + MAX_DRIVING_PER_SHIFT
        if rest >= total_drive_s:
            break
        stops.append(
            Stop("rest", rest, base_elapsed + SHIFT_ELAPSED, REST_LENGTH)
        )
        shift += 1
    return stops
