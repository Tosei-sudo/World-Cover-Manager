"""Integration tests for GET/POST/DELETE /api/scenes."""

import json

import pytest
from app.models import Tile

# 1°×1° square at origin in [lon, lat] (GeoJSON convention)
FOOTPRINT_GEOJSON = json.dumps({
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
})

SCENE_PAYLOAD = {
    "footprint_geojson": FOOTPRINT_GEOJSON,
    "captured_at": "2024-06-01T12:00:00Z",
    "cloud_cover_pct": 5.0,
}

ORDER_PAYLOAD = {"center_lat": 0.5, "center_lon": 0.5}


def _create_tile(db_session, **overrides):
    defaults = {
        "lat_min": 0.0, "lat_max": 1.0,
        "lon_min": 0.0, "lon_max": 1.0,
        "center_lat": 0.5, "center_lon": 0.5,
        "is_land": True,
    }
    defaults.update(overrides)
    tile = Tile(**defaults)
    db_session.add(tile)
    db_session.commit()
    db_session.refresh(tile)
    return tile


class TestCreateScene:
    def test_creates_scene_returns_201(self, client):
        res = client.post("/api/scenes", json=SCENE_PAYLOAD)
        assert res.status_code == 201
        assert "id" in res.json()

    def test_bbox_auto_computed_from_footprint(self, client):
        data = client.post("/api/scenes", json=SCENE_PAYLOAD).json()
        assert data["lat_min"] == pytest.approx(0.0)
        assert data["lat_max"] == pytest.approx(1.0)
        assert data["lon_min"] == pytest.approx(0.0)
        assert data["lon_max"] == pytest.approx(1.0)

    def test_invalid_geojson_returns_422(self, client):
        res = client.post("/api/scenes", json={**SCENE_PAYLOAD, "footprint_geojson": "not json"})
        assert res.status_code == 422

    def test_feature_wrapper_accepted(self, client):
        feature = json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
            },
            "properties": {},
        })
        res = client.post("/api/scenes", json={**SCENE_PAYLOAD, "footprint_geojson": feature})
        assert res.status_code == 201

    def test_scene_updates_tile_coverage(self, client, db_session):
        tile = _create_tile(db_session)
        client.post("/api/scenes", json=SCENE_PAYLOAD)
        db_session.refresh(tile)
        assert tile.coverage_pct > 0.0

    def test_overlapping_scene_marks_tile_completed(self, client, db_session):
        # Scene exactly covers the 1°×1° tile → ≥ COMPLETE_THRESHOLD_PCT
        tile = _create_tile(db_session)
        client.post("/api/scenes", json=SCENE_PAYLOAD)
        db_session.refresh(tile)
        assert tile.status == "COMPLETED"

    def test_linked_order_marked_completed(self, client):
        order = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        assert order["status"] == "PLANNED"
        client.post("/api/scenes", json={**SCENE_PAYLOAD, "order_id": order["id"]})
        updated = client.get(f"/api/orders/{order['id']}").json()
        assert updated["status"] == "COMPLETED"

    def test_already_terminal_order_not_changed(self, client):
        order = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        client.patch(f"/api/orders/{order['id']}", json={"status": "CANCELLED"})
        client.post("/api/scenes", json={**SCENE_PAYLOAD, "order_id": order["id"]})
        updated = client.get(f"/api/orders/{order['id']}").json()
        assert updated["status"] == "CANCELLED"

    def test_cloud_cover_pct_validation(self, client):
        # cloud_cover_pct > 100 should fail schema validation
        res = client.post("/api/scenes", json={**SCENE_PAYLOAD, "cloud_cover_pct": 101.0})
        assert res.status_code == 422


class TestListScenes:
    def test_empty_db(self, client):
        res = client.get("/api/scenes")
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_created_scenes(self, client):
        client.post("/api/scenes", json=SCENE_PAYLOAD)
        res = client.get("/api/scenes")
        assert len(res.json()) == 1

    def test_filter_by_order_id(self, client):
        order = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        client.post("/api/scenes", json={**SCENE_PAYLOAD, "order_id": order["id"]})
        client.post("/api/scenes", json=SCENE_PAYLOAD)  # no order

        res = client.get(f"/api/scenes?order_id={order['id']}")
        assert len(res.json()) == 1

    def test_limit_parameter(self, client):
        for _ in range(5):
            client.post("/api/scenes", json=SCENE_PAYLOAD)
        res = client.get("/api/scenes?limit=3")
        assert len(res.json()) == 3


class TestGetScene:
    def test_get_existing_scene(self, client):
        created = client.post("/api/scenes", json=SCENE_PAYLOAD).json()
        res = client.get(f"/api/scenes/{created['id']}")
        assert res.status_code == 200
        assert res.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client):
        res = client.get("/api/scenes/9999")
        assert res.status_code == 404


class TestDeleteScene:
    def test_delete_returns_204(self, client):
        created = client.post("/api/scenes", json=SCENE_PAYLOAD).json()
        assert client.delete(f"/api/scenes/{created['id']}").status_code == 204

    def test_scene_gone_after_delete(self, client):
        created = client.post("/api/scenes", json=SCENE_PAYLOAD).json()
        client.delete(f"/api/scenes/{created['id']}")
        assert client.get(f"/api/scenes/{created['id']}").status_code == 404

    def test_delete_recomputes_tile_coverage_to_zero(self, client, db_session):
        tile = _create_tile(db_session)
        scene = client.post("/api/scenes", json=SCENE_PAYLOAD).json()

        db_session.refresh(tile)
        assert tile.coverage_pct > 0.0  # scene applied

        client.delete(f"/api/scenes/{scene['id']}")
        db_session.refresh(tile)
        assert tile.coverage_pct == pytest.approx(0.0)

    def test_delete_nonexistent_returns_404(self, client):
        res = client.delete("/api/scenes/9999")
        assert res.status_code == 404
