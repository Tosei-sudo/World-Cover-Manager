# Historical ISS TLE (epoch 2008) used across tests.
# validate_tle only checks prefix and minimum length, not checksum.
TLE_LINE1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
TLE_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"

SAT_PAYLOAD = {
    "name": "Test Satellite",
    "norad_id": 25544,
    "tle_line1": TLE_LINE1,
    "tle_line2": TLE_LINE2,
    "swath_width_km": 200.0,
    "sensor_modes": "MULTISPECTRAL",
    "min_resolution_m": 5.0,
    "is_active": True,
}
