"""Integration tests for GET /api/stats/*."""

import pytest
from app.models import Tile

ORDER_PAYLOAD = {"center_lat": 35.0, "center_lon": 139.0}


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
    return tile


class TestCoverageStats:
    def test_empty_db_returns_zeros(self, client):
        res = client.get("/api/stats/coverage")
        assert res.status_code == 200
        data = res.json()
        assert data["total_land_tiles"] == 0
        assert data["completed_tiles"] == 0
        assert data["coverage_pct"] == pytest.approx(0.0)
        assert data["total_orders"] == 0

    def test_counts_by_status(self, client, db_session):
        _create_tile(db_session, status="COMPLETED")
        _create_tile(db_session, status="NOT_STARTED",
                     lat_min=10.0, lat_max=20.0, center_lat=15.0)
        _create_tile(db_session, status="IN_PROGRESS",
                     lat_min=20.0, lat_max=30.0, center_lat=25.0)

        data = client.get("/api/stats/coverage").json()
        assert data["total_land_tiles"] == 3
        assert data["completed_tiles"] == 1
        assert data["not_started_tiles"] == 1
        assert data["in_progress_tiles"] == 1

    def test_coverage_pct_when_all_completed(self, client, db_session):
        _create_tile(db_session, status="COMPLETED")
        _create_tile(db_session, status="COMPLETED",
                     lat_min=10.0, lat_max=20.0, center_lat=15.0)
        data = client.get("/api/stats/coverage").json()
        assert data["coverage_pct"] == pytest.approx(100.0)

    def test_coverage_pct_partial(self, client, db_session):
        _create_tile(db_session, status="COMPLETED")
        _create_tile(db_session, status="NOT_STARTED",
                     lat_min=10.0, lat_max=20.0, center_lat=15.0)
        data = client.get("/api/stats/coverage").json()
        assert data["coverage_pct"] == pytest.approx(50.0)

    def test_ocean_tiles_excluded_from_land_count(self, client, db_session):
        _create_tile(db_session, is_land=True)
        _create_tile(db_session, is_land=False,
                     lat_min=10.0, lat_max=20.0, center_lat=15.0)
        data = client.get("/api/stats/coverage").json()
        assert data["total_land_tiles"] == 1

    def test_orders_by_status_aggregation(self, client):
        client.post("/api/orders", json=ORDER_PAYLOAD)
        client.post("/api/orders", json=ORDER_PAYLOAD)
        data = client.get("/api/stats/coverage").json()
        assert data["total_orders"] == 2
        assert data["orders_by_status"]["PLANNED"] == 2

    def test_mixed_order_statuses(self, client):
        order = client.post("/api/orders", json=ORDER_PAYLOAD).json()
        client.patch(f"/api/orders/{order['id']}", json={"status": "COMPLETED"})
        client.post("/api/orders", json=ORDER_PAYLOAD)  # stays PLANNED

        data = client.get("/api/stats/coverage").json()
        assert data["orders_by_status"].get("PLANNED", 0) == 1
        assert data["orders_by_status"].get("COMPLETED", 0) == 1


class TestNextTargets:
    def test_empty_db(self, client):
        res = client.get("/api/stats/next-targets")
        assert res.status_code == 200
        assert res.json() == []

    def test_excludes_completed_tiles(self, client, db_session):
        _create_tile(db_session, status="NOT_STARTED")
        _create_tile(db_session, status="COMPLETED",
                     lat_min=10.0, lat_max=20.0, center_lat=15.0)
        data = client.get("/api/stats/next-targets").json()
        statuses = [t["status"] for t in data]
        assert "COMPLETED" not in statuses

    def test_returns_uncompleted_tiles(self, client, db_session):
        _create_tile(db_session, status="NOT_STARTED")
        res = client.get("/api/stats/next-targets")
        assert len(res.json()) == 1

    def test_limit_parameter(self, client, db_session):
        for i in range(5):
            _create_tile(
                db_session,
                lat_min=i * 10.0, lat_max=(i + 1) * 10.0,
                center_lat=i * 10.0 + 5.0,
            )
        res = client.get("/api/stats/next-targets?limit=3")
        assert len(res.json()) <= 3


class TestNextOpportunities:
    def test_empty_db_returns_empty_list(self, client):
        res = client.get("/api/stats/opportunities")
        assert res.status_code == 200
        assert res.json() == []

    def test_no_passes_returns_empty(self, client, db_session):
        # Tiles exist but no orbital passes computed → empty opportunities
        _create_tile(db_session, status="NOT_STARTED")
        res = client.get("/api/stats/opportunities")
        assert res.json() == []
