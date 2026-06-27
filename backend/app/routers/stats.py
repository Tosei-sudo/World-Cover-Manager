from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, Tile
from ..schemas import CoverageStats, TileOut

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
    """Return land tiles not yet started, ordered to suggest a sensible imaging sequence.

    Current heuristic: prefer lower absolute latitudes (equatorial regions have
    less cloud cover and more sunlight) and work outward.  This can be replaced
    with a more sophisticated algorithm without changing the API.
    """
    tiles = (
        db.query(Tile)
        .filter(Tile.is_land == True, Tile.status == "NOT_STARTED")  # noqa: E712
        .order_by(func.abs(Tile.center_lat))
        .limit(limit)
        .all()
    )
    return tiles
