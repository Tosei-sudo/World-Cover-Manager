"""
Automatic pass computation.

Called from:
  - routers/satellites.py  (background task on create / TLE update)
  - routers/stats.py       (inline before returning opportunities / next-targets)

The public surface is intentionally small:
  ensure_passes_fresh(db)   – compute for every stale active satellite
  compute_for_satellite(sat, db) – compute for one satellite (shared implementation)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import delete

from ..models import OrbitalPass, Satellite, Tile
from .orbit import (
    COMPUTE_WINDOW_HOURS,
    compute_passes,
    needs_recompute,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def compute_for_satellite(sat: Satellite, db: "Session", window_hours: int = COMPUTE_WINDOW_HOURS) -> int:
    """
    Propagate *sat*'s orbit and store the resulting passes.
    Returns the number of passes written.
    """
    tiles = (
        db.query(Tile)
        .filter(Tile.is_land == True, Tile.status != "COMPLETED")  # noqa: E712
        .all()
    )
    if not tiles:
        return 0

    pass_events, elapsed = compute_passes(
        tle_line1=sat.tle_line1,
        tle_line2=sat.tle_line2,
        sat_name=sat.name,
        swath_width_km=sat.swath_width_km,
        tiles=tiles,
        window_hours=window_hours,
    )

    # Replace all existing passes for this satellite
    db.execute(delete(OrbitalPass).where(OrbitalPass.satellite_id == sat.id))

    now = datetime.now(tz=timezone.utc)
    for ev in pass_events:
        db.add(OrbitalPass(
            satellite_id=sat.id,
            tile_id=ev.tile_id,
            pass_start=ev.pass_start,
            pass_end=ev.pass_end,
            duration_s=ev.duration_s,
            computed_at=now,
        ))

    db.commit()
    log.info("computed %d passes for satellite %d (%s) in %.2fs", len(pass_events), sat.id, sat.name, elapsed)
    return len(pass_events)


def ensure_passes_fresh(db: "Session") -> None:
    """
    For every active satellite, compute passes if the current data is stale.
    Runs synchronously; fast enough for a request-path call (~0.4 s per satellite).
    """
    active_sats = db.query(Satellite).filter(Satellite.is_active == True).all()  # noqa: E712
    for sat in active_sats:
        if needs_recompute(sat.id, db):
            log.info("auto-computing passes for satellite %d (%s)", sat.id, sat.name)
            try:
                compute_for_satellite(sat, db)
            except Exception:
                log.exception("pass computation failed for satellite %d", sat.id)


def bg_compute_for_satellite_id(sat_id: int) -> None:
    """
    Background-task wrapper: creates its own DB session so it can be called
    after a response has already been sent.
    """
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        sat = db.get(Satellite, sat_id)
        if sat and sat.is_active:
            compute_for_satellite(sat, db)
    except Exception:
        log.exception("background pass computation failed for satellite %d", sat_id)
    finally:
        db.close()
