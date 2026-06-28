"""Unit tests for app.services.orbit – TLE utilities and staleness checks."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.orbit import (
    RECOMPUTE_THRESHOLD_HOURS,
    needs_recompute,
    parse_tle_epoch,
    validate_tle,
)
from tests.constants import TLE_LINE1, TLE_LINE2


class TestParseTleEpoch:
    def test_2000s_epoch(self):
        # yy=24 < 57 → 2024
        line1 = "1 25544U 98067A   24001.00000000  .00000000  00000-0  10000-3 0  9990"
        epoch = parse_tle_epoch(line1)
        assert epoch.year == 2024
        assert epoch.month == 1
        assert epoch.day == 1
        assert epoch.tzinfo == timezone.utc

    def test_1900s_epoch(self):
        # yy=57 → 1957
        line1 = "1 25544U 98067A   57001.00000000  .00000000  00000-0  10000-3 0  9990"
        epoch = parse_tle_epoch(line1)
        assert epoch.year == 1957

    def test_day_fraction_maps_to_time(self):
        # Day 1.5 of year = noon on Jan 1
        line1 = "1 25544U 98067A   24001.50000000  .00000000  00000-0  10000-3 0  9990"
        epoch = parse_tle_epoch(line1)
        assert epoch.hour == 12

    def test_historical_tle(self):
        epoch = parse_tle_epoch(TLE_LINE1)
        assert epoch.year == 2008
        assert epoch.tzinfo == timezone.utc


class TestValidateTle:
    def test_valid_tle_passes(self):
        validate_tle(TLE_LINE1, TLE_LINE2)  # must not raise

    def test_wrong_prefix_line1(self):
        bad_l1 = "2 " + TLE_LINE1[2:]
        with pytest.raises(ValueError, match="line 1 must start"):
            validate_tle(bad_l1, TLE_LINE2)

    def test_wrong_prefix_line2(self):
        bad_l2 = "1 " + TLE_LINE2[2:]
        with pytest.raises(ValueError, match="line 2 must start"):
            validate_tle(TLE_LINE1, bad_l2)

    def test_line1_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            validate_tle("1 SHORT", TLE_LINE2)

    def test_line2_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            validate_tle(TLE_LINE1, "2 SHORT")

    def test_trailing_whitespace_is_stripped(self):
        # Trailing spaces must not cause the length check to fail
        validate_tle(TLE_LINE1 + "   ", TLE_LINE2 + "   ")


class TestNeedsRecompute:
    def test_no_passes_returns_true(self, db_session):
        assert needs_recompute(satellite_id=9999, db=db_session) is True

    def test_fresh_passes_return_false(self, db_session):
        from app.models import OrbitalPass, Satellite, Tile

        sat = Satellite(
            name="Fresh Sat", tle_line1=TLE_LINE1, tle_line2=TLE_LINE2,
            swath_width_km=200.0,
        )
        tile = Tile(
            lat_min=0.0, lat_max=10.0, lon_min=0.0, lon_max=10.0,
            center_lat=5.0, center_lon=5.0,
        )
        db_session.add_all([sat, tile])
        db_session.flush()

        future_end = (
            datetime.now(tz=timezone.utc)
            + timedelta(hours=RECOMPUTE_THRESHOLD_HOURS + 48)
        )
        db_session.add(OrbitalPass(
            satellite_id=sat.id, tile_id=tile.id,
            pass_start=datetime.now(tz=timezone.utc) + timedelta(hours=1),
            pass_end=future_end,
            duration_s=300,
        ))
        db_session.commit()

        assert needs_recompute(satellite_id=sat.id, db=db_session) is False

    def test_stale_passes_return_true(self, db_session):
        from app.models import OrbitalPass, Satellite, Tile

        sat = Satellite(
            name="Stale Sat", tle_line1=TLE_LINE1, tle_line2=TLE_LINE2,
            swath_width_km=200.0,
        )
        tile = Tile(
            lat_min=10.0, lat_max=20.0, lon_min=10.0, lon_max=20.0,
            center_lat=15.0, center_lon=15.0,
        )
        db_session.add_all([sat, tile])
        db_session.flush()

        # pass_end is within the recompute threshold → stale
        soon_end = (
            datetime.now(tz=timezone.utc)
            + timedelta(hours=RECOMPUTE_THRESHOLD_HOURS - 1)
        )
        db_session.add(OrbitalPass(
            satellite_id=sat.id, tile_id=tile.id,
            pass_start=datetime.now(tz=timezone.utc) + timedelta(hours=1),
            pass_end=soon_end,
            duration_s=300,
        ))
        db_session.commit()

        assert needs_recompute(satellite_id=sat.id, db=db_session) is True
