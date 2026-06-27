"""
Database initialisation script.

Generates a global lat/lon tile grid (default 10°×10°), classifies each tile
as land or ocean using a heuristic based on continental bounding boxes, and
seeds a few sample orders for demonstration purposes.

Usage:
    python init_db.py [--tile-size 10] [--reset]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Make the package importable when run directly
sys.path.insert(0, str(Path(__file__).parent))

from app.database import Base, SessionLocal, engine
from app.models import Order, Tile


# ---------------------------------------------------------------------------
# Land classification heuristic
# ---------------------------------------------------------------------------

def _classify(lat_c: float, lon_c: float) -> bool:
    """Return True if the tile centre is predominantly land.

    Based on approximate continental/regional bounding boxes.  Good enough
    for a demo; replace with a proper GIS polygon test for production.
    """
    # ── North America (including Central America) ────────────────────────────
    if 7 <= lat_c <= 72 and -168 <= lon_c <= -52:
        # Exclude most of Hudson Bay interior (~60–65°N, 85–95°W)
        if 58 <= lat_c <= 65 and -95 <= lon_c <= -78:
            return False
        # Exclude Gulf of Mexico core
        if 18 <= lat_c <= 28 and -97 <= lon_c <= -82:
            return False
        return True

    # ── Greenland ────────────────────────────────────────────────────────────
    if 58 <= lat_c <= 84 and -73 <= lon_c <= -12:
        return True

    # ── South America ────────────────────────────────────────────────────────
    if -57 <= lat_c <= 12 and -82 <= lon_c <= -33:
        return True

    # ── Europe (including British Isles and Scandinavia) ─────────────────────
    if 35 <= lat_c <= 72 and -12 <= lon_c <= 32:
        return True
    # Extend east for Russia / Ural
    if 50 <= lat_c <= 70 and 32 <= lon_c <= 62:
        return True

    # ── Africa ───────────────────────────────────────────────────────────────
    if -38 <= lat_c <= 38 and -18 <= lon_c <= 52:
        return True
    # Madagascar
    if -27 <= lat_c <= -12 and 43 <= lon_c <= 51:
        return True

    # ── Middle East / Arabian Peninsula ─────────────────────────────────────
    if 12 <= lat_c <= 38 and 32 <= lon_c <= 62:
        return True

    # ── Central & South Asia ────────────────────────────────────────────────
    if 5 <= lat_c <= 38 and 62 <= lon_c <= 100:
        # Exclude Bay of Bengal core
        if 5 <= lat_c <= 18 and 83 <= lon_c <= 98:
            return False
        return True

    # ── Russia / Siberia / Central Asia ─────────────────────────────────────
    if 48 <= lat_c <= 75 and 55 <= lon_c <= 180:
        return True

    # ── East Asia (China, Korea, Japan) ─────────────────────────────────────
    if 18 <= lat_c <= 52 and 100 <= lon_c <= 148:
        # Exclude Sea of Japan core
        if 35 <= lat_c <= 45 and 130 <= lon_c <= 140:
            return False
        return True

    # ── Southeast Asia mainland ──────────────────────────────────────────────
    if 3 <= lat_c <= 28 and 92 <= lon_c <= 110:
        return True

    # ── Maritime Southeast Asia (Indonesia, Philippines, etc.) ───────────────
    if -10 <= lat_c <= 18 and 95 <= lon_c <= 130:
        return True

    # ── Australia ────────────────────────────────────────────────────────────
    if -42 <= lat_c <= -12 and 112 <= lon_c <= 155:
        return True

    # ── New Zealand ──────────────────────────────────────────────────────────
    if -47 <= lat_c <= -35 and 166 <= lon_c <= 178:
        return True

    # ── Sri Lanka ────────────────────────────────────────────────────────────
    if 6 <= lat_c <= 10 and 79 <= lon_c <= 82:
        return True

    # ── Iceland ──────────────────────────────────────────────────────────────
    if 63 <= lat_c <= 67 and -25 <= lon_c <= -13:
        return True

    # ── Antarctica (partial – major coastlines included) ─────────────────────
    if lat_c <= -68:
        return True

    return False


# ---------------------------------------------------------------------------
# Tile generation
# ---------------------------------------------------------------------------

def generate_tiles(tile_size: float = 10.0) -> list[dict]:
    tiles = []
    lat = -90.0
    while lat < 90.0:
        lon = -180.0
        while lon < 180.0:
            lat_max = min(lat + tile_size, 90.0)
            lon_max = min(lon + tile_size, 180.0)
            c_lat = (lat + lat_max) / 2.0
            c_lon = (lon + lon_max) / 2.0
            tiles.append(
                dict(
                    lat_min=lat,
                    lat_max=lat_max,
                    lon_min=lon,
                    lon_max=lon_max,
                    center_lat=round(c_lat, 4),
                    center_lon=round(c_lon, 4),
                    tile_size=tile_size,
                    is_land=_classify(c_lat, c_lon),
                    status="NOT_STARTED",
                    coverage_count=0,
                )
            )
            lon += tile_size
        lat += tile_size
    return tiles


# ---------------------------------------------------------------------------
# Sample orders (demo data)
# ---------------------------------------------------------------------------

def _sample_orders(db, land_tiles: list[Tile]) -> None:
    now = datetime.utcnow()
    sensors = ["MULTISPECTRAL", "PANCHROMATIC", "SAR"]

    # Pick a few tiles to have in-progress or completed orders
    if not land_tiles:
        return

    samples = [
        dict(
            tile=land_tiles[0],
            status="COMPLETED",
            priority=8,
            sensor_mode="MULTISPECTRAL",
            resolution_m=5.0,
            max_cloud_pct=15.0,
            scheduled_start=now - timedelta(days=30),
            scheduled_end=now - timedelta(days=28),
            completed_at=now - timedelta(days=28),
            notes="First completed scene.",
        ),
        dict(
            tile=land_tiles[1] if len(land_tiles) > 1 else land_tiles[0],
            status="IN_PROGRESS",
            priority=7,
            sensor_mode="PANCHROMATIC",
            resolution_m=1.0,
            max_cloud_pct=10.0,
            scheduled_start=now - timedelta(days=2),
            scheduled_end=now + timedelta(days=1),
            completed_at=None,
            notes="High-res panchromatic pass.",
        ),
        dict(
            tile=land_tiles[2] if len(land_tiles) > 2 else land_tiles[0],
            status="PLANNED",
            priority=5,
            sensor_mode="SAR",
            resolution_m=10.0,
            max_cloud_pct=100.0,  # SAR is cloud-independent
            scheduled_start=now + timedelta(days=7),
            scheduled_end=now + timedelta(days=10),
            completed_at=None,
            notes="SAR pass, cloud-independent.",
        ),
    ]

    for s in samples:
        tile: Tile = s.pop("tile")
        order = Order(
            tile_id=tile.id,
            center_lat=tile.center_lat,
            center_lon=tile.center_lon,
            target_name=f"Demo – tile {tile.id}",
            **s,
        )
        db.add(order)
        # Reflect order status on tile
        if order.status == "COMPLETED":
            tile.status = "COMPLETED"
            tile.coverage_count += 1
            tile.last_captured_at = order.completed_at
        elif order.status == "IN_PROGRESS":
            tile.status = "IN_PROGRESS"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Initialise the World Cover Manager database")
    parser.add_argument("--tile-size", type=float, default=10.0, help="Tile size in degrees (default: 10)")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    args = parser.parse_args()

    if args.reset:
        print("Dropping all tables …")
        Base.metadata.drop_all(bind=engine)

    print("Creating tables …")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Tile).count() > 0 and not args.reset:
            print("Database already contains tiles. Use --reset to reinitialise.")
            return

        print(f"Generating {args.tile_size}°×{args.tile_size}° tile grid …")
        tile_dicts = generate_tiles(args.tile_size)
        land_count = sum(1 for t in tile_dicts if t["is_land"])
        print(f"  Total tiles : {len(tile_dicts)}")
        print(f"  Land tiles  : {land_count}")
        print(f"  Ocean tiles : {len(tile_dicts) - land_count}")

        tile_objects = [Tile(**d) for d in tile_dicts]
        db.add_all(tile_objects)
        db.flush()

        land_tiles = [t for t in tile_objects if t.is_land]
        print("Inserting sample orders …")
        _sample_orders(db, land_tiles)

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
