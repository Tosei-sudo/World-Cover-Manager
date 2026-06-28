"""Integration tests for GET/PATCH /api/tiles.

Tiles are created directly in the DB (there is no POST /api/tiles endpoint –
tiles are seeded by init_db.py).
"""

import pytest
from app.models import Tile


def _create_tile(db_session, **overrides):
    defaults = {
        "lat_min": 0.0, "lat_max": 10.0,
        "lon_min": 0.0, "lon_max": 10.0,
        "center_lat": 5.0, "center_lon": 5.0,
        "is_land": True, "status": "NOT_STARTED",
    }
    defaults.update(overrides)
    tile = Tile(**defaults)
    db_session.add(tile)
    db_session.commit()
    db_session.refresh(tile)
    return tile


class TestListTiles:
    def test_empty_db(self, client):
        res = client.get("/api/tiles")
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_all_tiles(self, client, db_session):
        _create_tile(db_session)
        _create_tile(db_session, lat_min=10.0, lat_max=20.0, center_lat=15.0)
        res = client.get("/api/tiles")
        assert res.status_code == 200
        assert len(res.json()) == 2

    def test_filter_is_land_true(self, client, db_session):
        _create_tile(db_session, is_land=True)
        _create_tile(db_session, is_land=False, lat_min=10.0, lat_max=20.0, center_lat=15.0)
        res = client.get("/api/tiles?is_land=true")
        data = res.json()
        assert len(data) == 1
        assert data[0]["is_land"] is True

    def test_filter_is_land_false(self, client, db_session):
        _create_tile(db_session, is_land=True)
        _create_tile(db_session, is_land=False, lat_min=10.0, lat_max=20.0, center_lat=15.0)
        res = client.get("/api/tiles?is_land=false")
        data = res.json()
        assert len(data) == 1
        assert data[0]["is_land"] is False

    def test_filter_status(self, client, db_session):
        _create_tile(db_session, status="NOT_STARTED")
        _create_tile(db_session, status="COMPLETED", lat_min=10.0, lat_max=20.0, center_lat=15.0)
        res = client.get("/api/tiles?status=COMPLETED")
        data = res.json()
        assert len(data) == 1
        assert data[0]["status"] == "COMPLETED"


class TestGetTile:
    def test_get_existing_tile(self, client, db_session):
        tile = _create_tile(db_session)
        res = client.get(f"/api/tiles/{tile.id}")
        assert res.status_code == 200
        assert res.json()["id"] == tile.id

    def test_response_contains_expected_fields(self, client, db_session):
        tile = _create_tile(db_session)
        data = client.get(f"/api/tiles/{tile.id}").json()
        for field in ("id", "lat_min", "lat_max", "lon_min", "lon_max",
                      "center_lat", "center_lon", "is_land", "status"):
            assert field in data

    def test_get_nonexistent_returns_404(self, client):
        res = client.get("/api/tiles/9999")
        assert res.status_code == 404


class TestPatchTile:
    def test_patch_status(self, client, db_session):
        tile = _create_tile(db_session)
        res = client.patch(f"/api/tiles/{tile.id}", json={"status": "IN_PROGRESS"})
        assert res.status_code == 200
        assert res.json()["status"] == "IN_PROGRESS"

    def test_patch_is_land(self, client, db_session):
        tile = _create_tile(db_session, is_land=True)
        res = client.patch(f"/api/tiles/{tile.id}", json={"is_land": False})
        assert res.status_code == 200
        assert res.json()["is_land"] is False

    def test_patch_notes(self, client, db_session):
        tile = _create_tile(db_session)
        res = client.patch(f"/api/tiles/{tile.id}", json={"notes": "Test note"})
        assert res.status_code == 200
        assert res.json()["notes"] == "Test note"

    def test_patch_coverage_count(self, client, db_session):
        tile = _create_tile(db_session)
        res = client.patch(f"/api/tiles/{tile.id}", json={"coverage_count": 3})
        assert res.status_code == 200
        assert res.json()["coverage_count"] == 3

    def test_patch_nonexistent_returns_404(self, client):
        res = client.patch("/api/tiles/9999", json={"status": "COMPLETED"})
        assert res.status_code == 404
