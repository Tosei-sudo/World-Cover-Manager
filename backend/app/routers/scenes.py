"""
Routes for scene footprint ingestion and querying.

POST /api/scenes
    Ingest an actual imaging footprint (GeoJSON Polygon).  Coverage for all
    tiles intersecting the footprint is recomputed using Shapely.  If the
    scene is tied to an order via order_id, that order is marked COMPLETED.

GET  /api/scenes
    List stored scenes, optionally filtered by order_id or satellite_id.

GET  /api/scenes/{id}
    Retrieve a single scene.

DELETE /api/scenes/{id}
    Delete a scene and recompute coverage for affected tiles.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, Scene
from ..schemas import SceneCreate, SceneOut
from ..services.coverage import footprint_bbox, recompute_tile_coverage, tiles_in_footprint_bbox

router = APIRouter(prefix="/scenes", tags=["scenes"])


@router.get("", response_model=list[SceneOut])
def list_scenes(
    order_id: Optional[int] = Query(None),
    satellite_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Scene)
    if order_id is not None:
        q = q.filter(Scene.order_id == order_id)
    if satellite_id is not None:
        q = q.filter(Scene.satellite_id == satellite_id)
    return q.order_by(Scene.captured_at.desc()).limit(limit).all()


@router.post("", response_model=SceneOut, status_code=201)
def create_scene(body: SceneCreate, db: Session = Depends(get_db)):
    """
    Ingest a scene footprint and recompute tile coverage.

    The footprint_geojson must be a valid GeoJSON Polygon or Feature.
    Coordinates follow the GeoJSON convention: [longitude, latitude].
    """
    try:
        lat_min, lat_max, lon_min, lon_max = footprint_bbox(body.footprint_geojson)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid footprint GeoJSON: {e}")

    scene = Scene(
        **body.model_dump(),
        lat_min=lat_min, lat_max=lat_max,
        lon_min=lon_min, lon_max=lon_max,
    )
    db.add(scene)
    db.flush()  # assign ID before recomputing coverage

    affected = tiles_in_footprint_bbox(lat_min, lat_max, lon_min, lon_max, db)
    for tile in affected:
        recompute_tile_coverage(tile, db)

    # Automatically mark the linked order COMPLETED (if not already terminal)
    if body.order_id:
        order = db.get(Order, body.order_id)
        if order and order.status not in ("COMPLETED", "FAILED", "CANCELLED"):
            order.status = "COMPLETED"
            if not order.completed_at:
                order.completed_at = datetime.now(tz=timezone.utc)

    db.commit()
    db.refresh(scene)
    return scene


@router.get("/{scene_id}", response_model=SceneOut)
def get_scene(scene_id: int, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.delete("/{scene_id}", status_code=204)
def delete_scene(scene_id: int, db: Session = Depends(get_db)):
    """Delete a scene and recompute coverage for all previously affected tiles."""
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    lat_min, lat_max = scene.lat_min, scene.lat_max
    lon_min, lon_max = scene.lon_min, scene.lon_max

    db.delete(scene)
    db.flush()

    for tile in tiles_in_footprint_bbox(lat_min, lat_max, lon_min, lon_max, db):
        recompute_tile_coverage(tile, db)

    db.commit()
