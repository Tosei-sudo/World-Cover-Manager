"""
Orbital mechanics service.

Uses skyfield + SGP4 to propagate satellite orbits from TLE data and
determine which ground tiles are covered by the satellite's swath during
each pass over a configurable time window.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

if TYPE_CHECKING:
    from ..models import Tile

# Singleton timescale – initialised once per process.
# builtin=True avoids downloading IERS data; sufficient for LEO propagation.
_ts = None


def _get_ts():
    global _ts
    if _ts is None:
        _ts = load.timescale(builtin=True)
    return _ts


# ── TLE utilities ─────────────────────────────────────────────────────────────

def parse_tle_epoch(line1: str) -> datetime:
    """Extract epoch from TLE line 1 (columns 18-32, zero-indexed)."""
    epoch_str = line1[18:32].strip()
    yy = int(epoch_str[:2])
    year = 2000 + yy if yy < 57 else 1900 + yy
    day_frac = float(epoch_str[2:])
    return datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_frac - 1)


def validate_tle(line1: str, line2: str) -> None:
    """Raise ValueError if the TLE lines are obviously malformed."""
    if not line1.startswith("1 "):
        raise ValueError("TLE line 1 must start with '1 '")
    if not line2.startswith("2 "):
        raise ValueError("TLE line 2 must start with '2 '")
    if len(line1.strip()) < 69:
        raise ValueError(f"TLE line 1 too short ({len(line1.strip())} chars, expected ≥69)")
    if len(line2.strip()) < 69:
        raise ValueError(f"TLE line 2 too short ({len(line2.strip())} chars, expected ≥69)")


# ── Pass computation ───────────────────────────────────────────────────────────

@dataclass
class PassEvent:
    tile_id: int
    pass_start: datetime
    pass_end: datetime
    duration_s: int


def compute_passes(
    tle_line1: str,
    tle_line2: str,
    sat_name: str,
    swath_width_km: float,
    tiles: list[Tile],
    window_hours: int = 168,
    step_s: int = 60,
) -> tuple[list[PassEvent], float]:
    """
    Propagate the satellite orbit and find which tiles are covered during each pass.

    Strategy
    --------
    For each propagation timestep the satellite subpoint (lat, lon) is compared
    against every tile's bounding box, expanded by half the swath width in each
    direction.  Contiguous covered timesteps form a single PassEvent.

    The bounding-box expansion is conservative: it slightly over-counts near the
    corners.  For a proper footprint polygon use a GIS library such as shapely.

    Returns
    -------
    (list[PassEvent], elapsed_seconds)
    """
    t0 = time.perf_counter()
    ts = _get_ts()
    sat = EarthSatellite(tle_line1, tle_line2, sat_name, ts)

    now = datetime.now(tz=timezone.utc)
    start_dt = now
    end_dt = now + timedelta(hours=window_hours)

    n_steps = int(window_hours * 3600 / step_s) + 1
    times_dt = [start_dt + timedelta(seconds=i * step_s) for i in range(n_steps)]
    t_sf = ts.from_datetimes(times_dt)

    # Vectorised ground-track computation
    geocentric = sat.at(t_sf)
    subpoint = wgs84.subpoint(geocentric)
    sat_lats = subpoint.latitude.degrees    # shape (n_steps,)
    sat_lons = subpoint.longitude.degrees   # shape (n_steps,)

    half_swath_lat = swath_width_km / 2.0 / 111.0  # degrees latitude (constant)

    results: list[PassEvent] = []

    for tile in tiles:
        # Longitude degrees per km varies with latitude
        cos_lat = math.cos(math.radians(tile.center_lat))
        half_swath_lon = swath_width_km / 2.0 / (111.0 * max(0.01, cos_lat))

        lat_ok = (sat_lats >= tile.lat_min - half_swath_lat) & \
                 (sat_lats <= tile.lat_max + half_swath_lat)
        lon_ok = (sat_lons >= tile.lon_min - half_swath_lon) & \
                 (sat_lons <= tile.lon_max + half_swath_lon)
        covered = lat_ok & lon_ok

        # Detect rising/falling edges to find pass boundaries
        padded = np.concatenate(([False], covered, [False]))
        changes = np.diff(padded.astype(np.int8))
        starts_idx = np.where(changes == 1)[0]
        ends_idx = np.where(changes == -1)[0]   # exclusive end

        for s, e in zip(starts_idx, ends_idx):
            e_inc = e - 1  # inclusive end index
            p_start = times_dt[s]
            p_end = times_dt[e_inc]
            dur = int((p_end - p_start).total_seconds())
            results.append(PassEvent(tile_id=tile.id, pass_start=p_start, pass_end=p_end, duration_s=dur))

    elapsed = time.perf_counter() - t0
    return results, elapsed


# ── Ground track ──────────────────────────────────────────────────────────────

def ground_track(
    tle_line1: str,
    tle_line2: str,
    sat_name: str,
    hours: float = 6.0,
    step_s: int = 120,
) -> list[dict]:
    """
    Return the satellite's ground track as a list of
    {"lat": float, "lon": float, "time": iso8601_str} points.
    """
    ts = _get_ts()
    sat = EarthSatellite(tle_line1, tle_line2, sat_name, ts)

    now = datetime.now(tz=timezone.utc)
    n_steps = int(hours * 3600 / step_s) + 1
    times_dt = [now + timedelta(seconds=i * step_s) for i in range(n_steps)]
    t_sf = ts.from_datetimes(times_dt)

    geocentric = sat.at(t_sf)
    subpoint = wgs84.subpoint(geocentric)
    lats = subpoint.latitude.degrees
    lons = subpoint.longitude.degrees

    return [
        {"lat": round(float(lats[i]), 4),
         "lon": round(float(lons[i]), 4),
         "time": times_dt[i].isoformat()}
        for i in range(n_steps)
    ]
