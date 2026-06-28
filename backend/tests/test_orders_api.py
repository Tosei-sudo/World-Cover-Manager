"""Integration tests for GET/POST/PATCH/DELETE /api/orders."""

import pytest
from app.models import Tile

ORDER_PAYLOAD = {
    "center_lat": 35.0,
    "center_lon": 139.0,
    "target_name": "Tokyo",
    "priority": 7,
    "max_cloud_pct": 10.0,
}


def _create_tile(db_session, **overrides):
    defaults = {
        "lat_min": 0.0, "lat_max": 10.0,
        "lon_min": 0.0, "lon_max": 10.0,
        "center_lat": 5.0, "center_lon": 5.0,
    }
    defaults.update(overrides)
    tile = Tile(**defaults)
    db_session.add(tile)
    db_session.commit()
    db_session.refresh(tile)
    return tile


class TestCreateOrder:
    def test_creates_order_returns_201(self, client):
        res = client.post("/api/orders", json=ORDER_PAYLOAD)
        assert res.status_code == 201
        data = res.json()
        assert data["center_lat"] == pytest.approx(35.0)
        assert data["status"] == "PLANNED"
        assert "id" in data

    def test_default_status_is_planned(self, client):
        res = client.post("/api/orders", json=ORDER_PAYLOAD)
        assert res.json()["status"] == "PLANNED"

    def test_order_on_not_started_tile_marks_in_progress(self, client, db_session):
        tile = _create_tile(db_session, status="NOT_STARTED")
        client.post("/api/orders", json={**ORDER_PAYLOAD, "tile_id": tile.id})
        db_session.refresh(tile)
        assert tile.status == "IN_PROGRESS"

    def test_order_on_completed_tile_leaves_status_unchanged(self, client, db_session):
        tile = _create_tile(db_session, status="COMPLETED")
        client.post("/api/orders", json={**ORDER_PAYLOAD, "tile_id": tile.id})
        db_session.refresh(tile)
        assert tile.status == "COMPLETED"

    def test_order_without_tile_id_is_accepted(self, client):
        res = client.post("/api/orders", json=ORDER_PAYLOAD)
        assert res.status_code == 201
        assert res.json()["tile_id"] is None

    def test_invalid_lat_out_of_range(self, client):
        res = client.post("/api/orders", json={**ORDER_PAYLOAD, "center_lat": 91.0})
        assert res.status_code == 422

    def test_invalid_lon_out_of_range(self, client):
        res = client.post("/api/orders", json={**ORDER_PAYLOAD, "center_lon": -181.0})
        assert res.status_code == 422

    def test_invalid_priority_out_of_range(self, client):
        res = client.post("/api/orders", json={**ORDER_PAYLOAD, "priority": 11})
        assert res.status_code == 422


class TestListOrders:
    def test_empty_db(self, client):
        res = client.get("/api/orders")
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_created_orders(self, client):
        client.post("/api/orders", json=ORDER_PAYLOAD)
        client.post("/api/orders", json=ORDER_PAYLOAD)
        res = client.get("/api/orders")
        assert len(res.json()) == 2

    def test_filter_by_status(self, client):
        client.post("/api/orders", json=ORDER_PAYLOAD)
        res = client.get("/api/orders?status=PLANNED")
        assert len(res.json()) == 1
        assert client.get("/api/orders?status=COMPLETED").json() == []

    def test_filter_by_tile_id(self, client, db_session):
        tile = _create_tile(db_session)
        client.post("/api/orders", json={**ORDER_PAYLOAD, "tile_id": tile.id})
        client.post("/api/orders", json=ORDER_PAYLOAD)  # no tile
        res = client.get(f"/api/orders?tile_id={tile.id}")
        assert len(res.json()) == 1


class TestGetOrder:
    def test_get_existing_order(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.get(f"/api/orders/{created['id']}")
        assert res.status_code == 200
        assert res.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client):
        res = client.get("/api/orders/9999")
        assert res.status_code == 404


class TestPatchOrder:
    def test_patch_status(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.patch(f"/api/orders/{created['id']}", json={"status": "SCHEDULED"})
        assert res.status_code == 200
        assert res.json()["status"] == "SCHEDULED"

    def test_terminal_status_auto_sets_completed_at(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.patch(f"/api/orders/{created['id']}", json={"status": "COMPLETED"})
        assert res.status_code == 200
        assert res.json()["completed_at"] is not None

    def test_failed_status_also_sets_completed_at(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.patch(f"/api/orders/{created['id']}", json={"status": "FAILED"})
        assert res.json()["completed_at"] is not None

    def test_completed_order_sets_tile_completed(self, client, db_session):
        tile = _create_tile(db_session, status="IN_PROGRESS")
        order = client.post("/api/orders", json={**ORDER_PAYLOAD, "tile_id": tile.id}).json()
        client.patch(f"/api/orders/{order['id']}", json={"status": "COMPLETED"})
        db_session.refresh(tile)
        assert tile.status == "COMPLETED"
        assert tile.coverage_count == 1
        assert tile.last_captured_at is not None

    def test_patch_notes(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.patch(f"/api/orders/{created['id']}", json={"notes": "urgent"})
        assert res.json()["notes"] == "urgent"

    def test_patch_nonexistent_returns_404(self, client):
        res = client.patch("/api/orders/9999", json={"status": "FAILED"})
        assert res.status_code == 404


class TestDeleteOrder:
    def test_delete_returns_204(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        res = client.delete(f"/api/orders/{created['id']}")
        assert res.status_code == 204

    def test_order_gone_after_delete(self, client):
        created = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        client.delete(f"/api/orders/{created['id']}")
        assert client.get(f"/api/orders/{created['id']}").status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        res = client.delete("/api/orders/9999")
        assert res.status_code == 404
