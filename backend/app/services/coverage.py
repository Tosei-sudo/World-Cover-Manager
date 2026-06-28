"""
Coverage computation using Shapely polygon intersection.

A scene footprint (a rotated polygon aligned with the orbit track) is
intersected with each tile's axis-aligned bounding box to compute how much
of the tile has been imaged.  Multiple scenes accumulate via unary_union
so overlapping passes don't double-count the same area.

Tiles whose accumulated coverage_pct reaches COMPLETE_THRESHOLD_PCT are
automatically transitioned to COMPLETED status.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from shapely.geometry import box, shape
from shapely.ops import unary_union

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

COMPLETE_THRESHOLD_PCT = 80.0


def parse_footprint(geojson_str: str):
    """Parse a GeoJSON geometry string (or Feature wrapper) to a Shapely geometry."""
    geom = json.loads(geojson_str)
    if geom.get("type") == "Feature":
        geom = geom["geometry"]
    return shape(geom)


def footprint_bbox(geojson_str: str) -> tuple[float, float, float, float]:
    """Return (lat_min, lat_max, lon_min, lon_max) bounding box of a footprint."""
    s = parse_footprint(geojson_str)
    lon_min, lat_min, lon_max, lat_max = s.bounds
    return lat_min, lat_max, lon_min, lon_max


def recompute_tile_coverage(tile, db: "Session") -> None:
    """Recompute coverage_pct for one tile from all stored scene footprints.

    Uses unary_union of per-scene intersections to avoid double-counting when
    two scenes overlap the same tile area.  Caller must commit after calling.
    """
    from ..models import Scene

    # Spatial pre-filter using stored bbox columns
    candidates = (
        db.query(Scene)
        .filter(
            Scene.lat_min <= tile.lat_max,
            Scene.lat_max >= tile.lat_min,
            Scene.lon_min <= tile.lon_max,
            Scene.lon_max >= tile.lon_min,
        )
        .all()
    )

    tile_geom = box(tile.lon_min, tile.lat_min, tile.lon_max, tile.lat_max)
    tile_area = tile_geom.area
    if tile_area == 0:
        return

    intersections = []
    for scene in candidates:
        try:
            fp = parse_footprint(scene.footprint_geojson)
            inter = fp.intersection(tile_geom)
            if not inter.is_empty:
                intersections.append(inter)
        except Exception:
            continue

    if intersections:
        union = unary_union(intersections)
        tile.coverage_pct = min(100.0, round(union.area / tile_area * 100.0, 2))
    else:
        tile.coverage_pct = 0.0

    if tile.coverage_pct >= COMPLETE_THRESHOLD_PCT:
        if tile.status != "COMPLETED":
            tile.status = "COMPLETED"
            tile.coverage_count = (tile.coverage_count or 0) + 1
            if not tile.last_captured_at:
                tile.last_captured_at = datetime.now(tz=timezone.utc)
    elif tile.coverage_pct > 0:
        if tile.status == "NOT_STARTED":
            tile.status = "IN_PROGRESS"
    else:
        if tile.status == "IN_PROGRESS":
            tile.status = "NOT_STARTED"


def tiles_in_footprint_bbox(
    lat_min: float, lat_max: float, lon_min: float, lon_max: float,
    db: "Session",
):
    """Return all land tiles whose bounding box overlaps the given bbox."""
    from ..models import Tile

    return (
        db.query(Tile)
        .filter(
            Tile.is_land == True,           # noqa: E712
            Tile.lat_min <= lat_max,
            Tile.lat_max >= lat_min,
            Tile.lon_min <= lon_max,
            Tile.lon_max >= lon_min,
        )
        .all()
    )
