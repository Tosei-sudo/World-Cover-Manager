"""Unit tests for app.services.coverage."""

import json
from datetime import datetime, timezone

import pytest

from app.services.coverage import (
    COMPLETE_THRESHOLD_PCT,
    footprint_bbox,
    parse_footprint,
    recompute_tile_coverage,
    tiles_in_footprint_bbox,
)

# 1°×1° square at origin in [lon, lat] order (GeoJSON convention)
SQUARE_GEOJSON = json.dumps({
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
})

FEATURE_GEOJSON = json.dumps({
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
    },
    "properties": {},
})


class TestParseFootprint:
    def test_polygon_geometry(self):
        geom = parse_footprint(SQUARE_GEOJSON)
        assert not geom.is_empty
        assert geom.area == pytest.approx(1.0)

    def test_feature_wrapper(self):
        geom = parse_footprint(FEATURE_GEOJSON)
        assert not geom.is_empty
        assert geom.area == pytest.approx(1.0)

    def test_bounds(self):
        geom = parse_footprint(SQUARE_GEOJSON)
        assert geom.bounds == (0.0, 0.0, 1.0, 1.0)


class TestFootprintBbox:
    def test_bbox_values(self):
        lat_min, lat_max, lon_min, lon_max = footprint_bbox(SQUARE_GEOJSON)
        assert lat_min == pytest.approx(0.0)
        assert lat_max == pytest.approx(1.0)
        assert lon_min == pytest.approx(0.0)
        assert lon_max == pytest.approx(1.0)

    def test_bbox_non_origin(self):
        geojson = json.dumps({
            "type": "Polygon",
            "coordinates": [
                [[10.0, 20.0], [15.0, 20.0], [15.0, 25.0], [10.0, 25.0], [10.0, 20.0]]
            ],
        })
        lat_min, lat_max, lon_min, lon_max = footprint_bbox(geojson)
        assert lat_min == pytest.approx(20.0)
        assert lat_max == pytest.approx(25.0)
        assert lon_min == pytest.approx(10.0)
        assert lon_max == pytest.approx(15.0)


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_tile(db_session, lat_min=0.0, lat_max=1.0, lon_min=0.0, lon_max=1.0, **kwargs):
    from app.models import Tile

    tile = Tile(
        lat_min=lat_min, lat_max=lat_max,
        lon_min=lon_min, lon_max=lon_max,
        center_lat=(lat_min + lat_max) / 2,
        center_lon=(lon_min + lon_max) / 2,
        **kwargs,
    )
    db_session.add(tile)
    db_session.flush()
    return tile


def _make_scene(db_session, geojson=SQUARE_GEOJSON):
    from app.models import Scene

    lat_min, lat_max, lon_min, lon_max = footprint_bbox(geojson)
    scene = Scene(
        footprint_geojson=geojson,
        captured_at=datetime.now(tz=timezone.utc),
        lat_min=lat_min, lat_max=lat_max,
        lon_min=lon_min, lon_max=lon_max,
    )
    db_session.add(scene)
    db_session.flush()
    return scene


# ── recompute_tile_coverage ────────────────────────────────────────────────────

class TestRecomputeTileCoverage:
    def test_full_coverage_marks_completed(self, db_session):
        tile = _make_tile(db_session, 0.0, 1.0, 0.0, 1.0)
        _make_scene(db_session)  # scene exactly matches tile
        recompute_tile_coverage(tile, db_session)
        assert tile.coverage_pct == pytest.approx(100.0)
        assert tile.status == "COMPLETED"

    def test_no_overlapping_scene_stays_not_started(self, db_session):
        tile = _make_tile(db_session, 5.0, 6.0, 5.0, 6.0)  # far from scene
        _make_scene(db_session)  # scene at 0-1°
        recompute_tile_coverage(tile, db_session)
        assert tile.coverage_pct == pytest.approx(0.0)
        assert tile.status == "NOT_STARTED"

    def test_partial_coverage_marks_in_progress(self, db_session):
        # 2°×2° tile, 1°×1° scene → ~25 % coverage
        tile = _make_tile(db_session, 0.0, 2.0, 0.0, 2.0)
        _make_scene(db_session)
        recompute_tile_coverage(tile, db_session)
        assert 0.0 < tile.coverage_pct < COMPLETE_THRESHOLD_PCT
        assert tile.status == "IN_PROGRESS"

    def test_no_double_counting_for_overlapping_scenes(self, db_session):
        tile = _make_tile(db_session, 0.0, 1.0, 0.0, 1.0)
        _make_scene(db_session)
        _make_scene(db_session)  # identical footprint
        recompute_tile_coverage(tile, db_session)
        # unary_union of two identical polygons is still 100 %, not 200 %
        assert tile.coverage_pct == pytest.approx(100.0)

    def test_in_progress_reverts_to_not_started_when_no_scenes(self, db_session):
        tile = _make_tile(db_session, 0.0, 1.0, 0.0, 1.0)
        tile.status = "IN_PROGRESS"
        tile.coverage_pct = 50.0
        db_session.commit()
        # No scenes in DB → coverage 0 → revert status
        recompute_tile_coverage(tile, db_session)
        assert tile.coverage_pct == pytest.approx(0.0)
        assert tile.status == "NOT_STARTED"

    def test_coverage_count_incremented_on_first_completion(self, db_session):
        tile = _make_tile(db_session, 0.0, 1.0, 0.0, 1.0)
        _make_scene(db_session)
        recompute_tile_coverage(tile, db_session)
        assert tile.coverage_count == 1

    def test_last_captured_at_set_on_completion(self, db_session):
        tile = _make_tile(db_session, 0.0, 1.0, 0.0, 1.0)
        _make_scene(db_session)
        recompute_tile_coverage(tile, db_session)
        assert tile.last_captured_at is not None


# ── tiles_in_footprint_bbox ────────────────────────────────────────────────────

class TestTilesInFootprintBbox:
    def test_overlapping_land_tile_included(self, db_session):
        from app.models import Tile

        tile = Tile(
            lat_min=0.0, lat_max=1.0, lon_min=0.0, lon_max=1.0,
            center_lat=0.5, center_lon=0.5, is_land=True,
        )
        db_session.add(tile)
        db_session.commit()

        result = tiles_in_footprint_bbox(0.0, 1.0, 0.0, 1.0, db_session)
        assert len(result) == 1
        assert result[0].id == tile.id

    def test_non_overlapping_tile_excluded(self, db_session):
        from app.models import Tile

        tile = Tile(
            lat_min=10.0, lat_max=11.0, lon_min=10.0, lon_max=11.0,
            center_lat=10.5, center_lon=10.5, is_land=True,
        )
        db_session.add(tile)
        db_session.commit()

        result = tiles_in_footprint_bbox(0.0, 1.0, 0.0, 1.0, db_session)
        assert result == []

    def test_ocean_tile_excluded(self, db_session):
        from app.models import Tile

        tile = Tile(
            lat_min=0.0, lat_max=1.0, lon_min=0.0, lon_max=1.0,
            center_lat=0.5, center_lon=0.5, is_land=False,
        )
        db_session.add(tile)
        db_session.commit()

        result = tiles_in_footprint_bbox(0.0, 1.0, 0.0, 1.0, db_session)
        assert result == []

    def test_multiple_overlapping_tiles_all_returned(self, db_session):
        from app.models import Tile

        tiles = [
            Tile(lat_min=0.0, lat_max=1.0, lon_min=0.0, lon_max=1.0,
                 center_lat=0.5, center_lon=0.5, is_land=True),
            Tile(lat_min=0.5, lat_max=1.5, lon_min=0.5, lon_max=1.5,
                 center_lat=1.0, center_lon=1.0, is_land=True),
        ]
        db_session.add_all(tiles)
        db_session.commit()

        result = tiles_in_footprint_bbox(0.0, 1.5, 0.0, 1.5, db_session)
        assert len(result) == 2
