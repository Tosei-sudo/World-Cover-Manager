from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Satellite, Tile
from ..schemas import SatelliteCreate, SatelliteOut, SatellitePatch
from ..services.auto_pass import bg_compute_for_satellite_id
from ..services.orbit import parse_tle_epoch, validate_tle

router = APIRouter(prefix="/satellites", tags=["satellites"])


def _apply_tle(sat: Satellite, line1: str, line2: str) -> None:
    validate_tle(line1, line2)
    sat.tle_line1 = line1.strip()
    sat.tle_line2 = line2.strip()
    sat.tle_epoch = parse_tle_epoch(line1)
    sat.tle_updated_at = datetime.utcnow()


def _swath_warning(swath_km: float, db: Session) -> str | None:
    """Return a warning string if swath_km is narrower than the current tile grid."""
    tile_size_deg = db.query(Tile.tile_size).limit(1).scalar()
    if tile_size_deg is None:
        return None
    tile_width_km = tile_size_deg * 111.0
    if swath_km < tile_width_km:
        return (
            f"Swath width {swath_km} km is narrower than the tile grid "
            f"({tile_size_deg}° ≈ {tile_width_km:.0f} km). "
            "A single pass will not cover a full tile. "
            "Consider re-initialising with a smaller tile size "
            f"(e.g. python init_db.py --reset, which will auto-select ≤{swath_km/111:.1f}°)."
        )
    return None


def _sat_out(sat: Satellite, db: Session) -> SatelliteOut:
    out = SatelliteOut.model_validate(sat)
    out.tile_coverage_warning = _swath_warning(sat.swath_width_km, db)
    return out


@router.get("", response_model=list[SatelliteOut])
def list_satellites(
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Satellite)
    if is_active is not None:
        q = q.filter(Satellite.is_active == is_active)
    sats = q.order_by(Satellite.id).all()
    return [_sat_out(s, db) for s in sats]


@router.post("", response_model=SatelliteOut, status_code=201)
def create_satellite(
    body: SatelliteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        validate_tle(body.tle_line1, body.tle_line2)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    sat = Satellite(**body.model_dump())
    sat.tle_line1 = body.tle_line1.strip()
    sat.tle_line2 = body.tle_line2.strip()
    sat.tle_epoch = parse_tle_epoch(body.tle_line1)
    sat.tle_updated_at = datetime.utcnow()
    db.add(sat)
    db.commit()
    db.refresh(sat)

    background_tasks.add_task(bg_compute_for_satellite_id, sat.id)
    return _sat_out(sat, db)


@router.get("/{sat_id}", response_model=SatelliteOut)
def get_satellite(sat_id: int, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return _sat_out(sat, db)


@router.patch("/{sat_id}", response_model=SatelliteOut)
def patch_satellite(
    sat_id: int,
    body: SatellitePatch,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")

    updates = body.model_dump(exclude_unset=True)
    tle_changed = False

    line1 = updates.pop("tle_line1", None)
    line2 = updates.pop("tle_line2", None)
    if line1 or line2:
        new_l1 = line1 or sat.tle_line1
        new_l2 = line2 or sat.tle_line2
        try:
            _apply_tle(sat, new_l1, new_l2)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        tle_changed = True

    for field, value in updates.items():
        setattr(sat, field, value)

    db.commit()
    db.refresh(sat)

    if tle_changed and sat.is_active:
        background_tasks.add_task(bg_compute_for_satellite_id, sat.id)

    return _sat_out(sat, db)


@router.delete("/{sat_id}", status_code=204)
def delete_satellite(sat_id: int, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    db.delete(sat)
    db.commit()


@router.delete("/{sat_id}", status_code=204)
def delete_satellite(sat_id: int, db: Session = Depends(get_db)):
    sat = db.get(Satellite, sat_id)
    if not sat:
        raise HTTPException(status_code=404, detail="Satellite not found")
    db.delete(sat)
    db.commit()
