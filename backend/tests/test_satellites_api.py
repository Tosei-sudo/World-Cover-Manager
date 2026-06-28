"""Integration tests for GET/POST/PATCH/DELETE /api/satellites."""

import pytest
from tests.constants import SAT_PAYLOAD, TLE_LINE1, TLE_LINE2


class TestListSatellites:
    def test_empty_db(self, client):
        res = client.get("/api/satellites")
        assert res.status_code == 200
        assert res.json() == []

    def test_returns_created_satellite(self, client):
        client.post("/api/satellites", json=SAT_PAYLOAD)
        res = client.get("/api/satellites")
        assert res.status_code == 200
        assert len(res.json()) == 1

    def test_filter_active_true(self, client):
        client.post("/api/satellites", json=SAT_PAYLOAD)
        client.post("/api/satellites", json={
            **SAT_PAYLOAD, "name": "Inactive", "norad_id": 99999, "is_active": False,
        })
        res = client.get("/api/satellites?is_active=true")
        assert res.status_code == 200
        assert all(s["is_active"] for s in res.json())

    def test_filter_active_false(self, client):
        client.post("/api/satellites", json=SAT_PAYLOAD)
        client.post("/api/satellites", json={
            **SAT_PAYLOAD, "name": "Inactive", "norad_id": 99999, "is_active": False,
        })
        res = client.get("/api/satellites?is_active=false")
        assert res.status_code == 200
        assert all(not s["is_active"] for s in res.json())


class TestCreateSatellite:
    def test_creates_satellite_returns_201(self, client):
        res = client.post("/api/satellites", json=SAT_PAYLOAD)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == SAT_PAYLOAD["name"]
        assert data["swath_width_km"] == SAT_PAYLOAD["swath_width_km"]
        assert "id" in data

    def test_tle_epoch_is_parsed(self, client):
        res = client.post("/api/satellites", json=SAT_PAYLOAD)
        assert res.status_code == 201
        assert res.json()["tle_epoch"] is not None

    def test_invalid_line1_prefix_returns_422(self, client):
        payload = {**SAT_PAYLOAD, "tle_line1": "X " + TLE_LINE1[2:]}
        res = client.post("/api/satellites", json=payload)
        assert res.status_code == 422

    def test_invalid_line2_prefix_returns_422(self, client):
        payload = {**SAT_PAYLOAD, "tle_line2": "X " + TLE_LINE2[2:]}
        res = client.post("/api/satellites", json=payload)
        assert res.status_code == 422

    def test_tle_line_too_short_returns_422(self, client):
        payload = {**SAT_PAYLOAD, "tle_line1": "1 SHORT"}
        res = client.post("/api/satellites", json=payload)
        assert res.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        payload = {k: v for k, v in SAT_PAYLOAD.items() if k != "tle_line1"}
        res = client.post("/api/satellites", json=payload)
        assert res.status_code == 422


class TestGetSatellite:
    def test_get_existing_satellite(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        res = client.get(f"/api/satellites/{created['id']}")
        assert res.status_code == 200
        assert res.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client):
        res = client.get("/api/satellites/9999")
        assert res.status_code == 404


class TestPatchSatellite:
    def test_patch_name(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        res = client.patch(f"/api/satellites/{created['id']}", json={"name": "Updated"})
        assert res.status_code == 200
        assert res.json()["name"] == "Updated"

    def test_patch_is_active(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        res = client.patch(f"/api/satellites/{created['id']}", json={"is_active": False})
        assert res.status_code == 200
        assert res.json()["is_active"] is False

    def test_patch_swath_width(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        res = client.patch(f"/api/satellites/{created['id']}", json={"swath_width_km": 500.0})
        assert res.status_code == 200
        assert res.json()["swath_width_km"] == pytest.approx(500.0)

    def test_patch_nonexistent_returns_404(self, client):
        res = client.patch("/api/satellites/9999", json={"name": "X"})
        assert res.status_code == 404


class TestDeleteSatellite:
    def test_delete_returns_204(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        res = client.delete(f"/api/satellites/{created['id']}")
        assert res.status_code == 204

    def test_satellite_gone_after_delete(self, client):
        created = client.post("/api/satellites", json=SAT_PAYLOAD).json()
        client.delete(f"/api/satellites/{created['id']}")
        res = client.get(f"/api/satellites/{created['id']}")
        assert res.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        res = client.delete("/api/satellites/9999")
        assert res.status_code == 404
