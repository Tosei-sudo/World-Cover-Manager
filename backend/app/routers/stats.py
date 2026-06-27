from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, OrbitalPass, Satellite, Tile
from ..schemas import CoverageStats, PassOpportunity, TileOut
from ..services.auto_pass import ensure_passes_fresh

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/coverage", response_model=CoverageStats)
def coverage_stats(db: Session = Depends(get_db)):
    land_tiles = db.query(Tile).filter(Tile.is_land == True).all()  # noqa: E712
    total = len(land_tiles)
    completed = sum(1 for t in land_tiles if t.status == "COMPLETED")
    in_progress = sum(1 for t in land_tiles if t.status == "IN_PROGRESS")
    not_started = sum(1 for t in land_tiles if t.status == "NOT_STARTED")

    orders_by_status: dict[str, int] = {}
    for status, count in db.query(Order.status, func.count()).group_by(Order.status).all():
        orders_by_status[status] = count

    return CoverageStats(
        total_land_tiles=total,
        completed_tiles=completed,
        in_progress_tiles=in_progress,
        not_started_tiles=not_started,
        coverage_pct=round(completed / total * 100, 2) if total else 0.0,
        total_orders=sum(orders_by_status.values()),
        orders_by_status=orders_by_status,
    )


@router.get("/next-targets", response_model=list[TileOut])
def next_targets(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return uncovered land tiles sorted by earliest upcoming pass.
    Falls back to latitude heuristic when no pass data is available.
    Automatically recomputes passes for stale satellites before querying.
    """
    ensure_passes_fresh(db)

    now = datetime.now(tz=timezone.utc)

    tiles_with_pass = (
        db.query(Tile, func.min(OrbitalPass.pass_start).label("next_pass"))
        .join(OrbitalPass, OrbitalPass.tile_id == Tile.id)
        .filter(
            Tile.is_land == True,               # noqa: E712
            Tile.status == "NOT_STARTED",
            OrbitalPass.pass_start > now,
        )
        .group_by(Tile.id)
        .order_by("next_pass")
        .limit(limit)
        .all()
    )

    tile_ids_with_pass = {t.id for t, _ in tiles_with_pass}
    result_tiles = [t for t, _ in tiles_with_pass]

    remaining = limit - len(result_tiles)
    if remaining > 0:
        fallback = (
            db.query(Tile)
            .filter(
                Tile.is_land == True,           # noqa: E712
                Tile.status == "NOT_STARTED",
                ~Tile.id.in_(tile_ids_with_pass),
            )
            .order_by(func.abs(Tile.center_lat))
            .limit(remaining)
            .all()
        )
        result_tiles.extend(fallback)

    return result_tiles


@router.get("/opportunities", response_model=list[PassOpportunity])
def next_opportunities(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Return the N soonest imaging opportunities for uncovered land tiles.
    Automatically recomputes passes for stale satellites before querying.
    """
    ensure_passes_fresh(db)

    now = datetime.now(tz=timezone.utc)

    rows = (
        db.query(OrbitalPass, Tile, Satellite)
        .join(Tile, Tile.id == OrbitalPass.tile_id)
        .join(Satellite, Satellite.id == OrbitalPass.satellite_id)
        .filter(
            Tile.is_land == True,               # noqa: E712
            Tile.status == "NOT_STARTED",
            OrbitalPass.pass_start > now,
            Satellite.is_active == True,         # noqa: E712
        )
        .order_by(OrbitalPass.pass_start)
        .limit(limit)
        .all()
    )

    return [
        PassOpportunity(
            tile=TileOut.model_validate(tile),
            satellite=sat,
            pass_start=op.pass_start,
            pass_end=op.pass_end,
            duration_s=op.duration_s,
        )
        for op, tile, sat in rows
    ]
