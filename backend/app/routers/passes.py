"""
Routes for computing and querying orbital passes.

POST /api/satellites/{id}/compute-passes
    Propagates the satellite orbit over the requested window and stores the
    predicted passes in the orbital_passes table.  Old passes for this
    satellite are deleted first so the table stays current.

GET  /api/passes
    Query stored passes (filter by satellite, tile, time range).

GET  /api/satellites/{id}/ground-track
    Return the predicted ground track as a lat/lon/time array for map display.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import OrbitalPass, Satellite, Tile
from ..schemas import ComputePassesResult, OrbitalPassOut
from ..services.orbit import compute_passes, ground_track

router = APIRouter(tags=["passes"])


# ── Compute ───────────────────────────────────────────────────────────────────

@router.post(
    "/satellites/{sat_id}/compute-passes",
    response_model=ComputePassesResult,
)
def trigger_compute_passes(
    sat_id: int,
    window_hours: int = Query(168, ge=1, le=720, description="Look-ahead window in hours"),
    step_s: int = Query(60, ge=10, le=300, description="Propagation step in seconds"),
    db: Session = Depends(get_db),
):
    """
    (Re)compute passes for a satellite over the next *window_hours* hours.

    All previously stored passes for this satellite are replaced.
    Computation is synchronous; for a 7-day window at 60s step it typically
    completes in < 3 seconds thanks to NumPy vectorisation.
    """
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")

    # Only check land tiles that are not yet completed
    tiles = (
        db.query(Tile)
        .filter(Tile.is_land == True, Tile.status != "COMPLETED")  # noqa: E712
        .all()
    )

    if not tiles:
        return ComputePassesResult(
            satellite_id=sat_id,
            window_hours=window_hours,
            tiles_checked=0,
            passes_found=0,
            elapsed_s=0.0,
        )

    try:
        pass_events, elapsed = compute_passes(
            tle_line1=sat.tle_line1,
            tle_line2=sat.tle_line2,
            sat_name=sat.name,
            swath_width_km=sat.swath_width_km,
            tiles=tiles,
            window_hours=window_hours,
            step_s=step_s,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orbit propagation failed: {e}")

    # Replace existing passes for this satellite
    db.execute(delete(OrbitalPass).where(OrbitalPass.satellite_id == sat_id))

    for ev in pass_events:
        db.add(OrbitalPass(
            satellite_id=sat_id,
            tile_id=ev.tile_id,
            pass_start=ev.pass_start,
            pass_end=ev.pass_end,
            duration_s=ev.duration_s,
            computed_at=datetime.now(tz=timezone.utc),
        ))

    db.commit()

    return ComputePassesResult(
        satellite_id=sat_id,
        window_hours=window_hours,
        tiles_checked=len(tiles),
        passes_found=len(pass_events),
        elapsed_s=round(elapsed, 3),
    )


# ── Query ─────────────────────────────────────────────────────────────────────

@router.get("/passes", response_model=list[OrbitalPassOut])
def list_passes(
    satellite_id: int | None = Query(None),
    tile_id: int | None = Query(None),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    now = datetime.now(tz=timezone.utc)
    q = db.query(OrbitalPass).filter(OrbitalPass.pass_end >= now)
    if satellite_id is not None:
        q = q.filter(OrbitalPass.satellite_id == satellite_id)
    if tile_id is not None:
        q = q.filter(OrbitalPass.tile_id == tile_id)
    if after:
        q = q.filter(OrbitalPass.pass_start >= after)
    if before:
        q = q.filter(OrbitalPass.pass_start <= before)
    return q.order_by(OrbitalPass.pass_start).limit(limit).all()


# ── Ground track ──────────────────────────────────────────────────────────────

@router.get("/satellites/{sat_id}/ground-track")
def get_ground_track(
    sat_id: int,
    hours: float = Query(6.0, ge=0.5, le=24.0),
    step_s: int = Query(120, ge=30, le=600),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Return the predicted ground track as [{lat, lon, time}, …] for map display."""
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    try:
        return ground_track(sat.tle_line1, sat.tle_line2, sat.name, hours, step_s)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ground-track computation failed: {e}")
