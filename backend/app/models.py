from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class Satellite(Base):
    """A satellite that can be tasked for imaging."""
    __tablename__ = "satellites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    norad_id = Column(Integer, nullable=True, unique=True, index=True)

    # TLE (Two-Line Element set)
    tle_line1 = Column(String(100), nullable=False)
    tle_line2 = Column(String(100), nullable=False)
    tle_epoch = Column(DateTime, nullable=True)         # Parsed from TLE
    tle_updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    # Sensor characteristics
    swath_width_km = Column(Float, nullable=False)      # Total cross-track swath (km)
    sensor_modes = Column(String(500), nullable=True)   # Comma-separated: "MULTISPECTRAL,PANCHROMATIC"
    min_resolution_m = Column(Float, nullable=True)     # Best achievable GSD (m)

    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    orders = relationship("Order", back_populates="satellite")
    passes = relationship("OrbitalPass", back_populates="satellite", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="satellite")


class OrbitalPass(Base):
    """A predicted pass of a satellite over a tile, computed from TLE + swath."""
    __tablename__ = "orbital_passes"

    id = Column(Integer, primary_key=True, index=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    tile_id = Column(Integer, ForeignKey("tiles.id", ondelete="CASCADE"), nullable=False)

    pass_start = Column(DateTime, nullable=False)
    pass_end = Column(DateTime, nullable=False)
    duration_s = Column(Integer, nullable=False)        # pass_end - pass_start in seconds
    computed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    satellite = relationship("Satellite", back_populates="passes")
    tile = relationship("Tile", back_populates="passes")

    __table_args__ = (
        UniqueConstraint("satellite_id", "tile_id", "pass_start", name="uq_pass"),
        Index("ix_pass_start", "pass_start"),
        Index("ix_pass_sat_tile", "satellite_id", "tile_id"),
    )


class Tile(Base):
    """One cell in the global lat/lon grid. Only land tiles need coverage."""
    __tablename__ = "tiles"

    id = Column(Integer, primary_key=True, index=True)
    lat_min = Column(Float, nullable=False)
    lat_max = Column(Float, nullable=False)
    lon_min = Column(Float, nullable=False)
    lon_max = Column(Float, nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    tile_size = Column(Float, nullable=False, default=10.0)

    is_land = Column(Boolean, nullable=False, default=True)
    # NOT_STARTED | IN_PROGRESS | COMPLETED
    status = Column(String(20), nullable=False, default="NOT_STARTED")
    coverage_count = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)
    last_captured_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="tile")
    passes = relationship("OrbitalPass", back_populates="tile", cascade="all, delete-orphan")


class Scene(Base):
    """An actual captured image footprint ingested after execution of an order.

    The footprint is stored as a GeoJSON Polygon (coordinates in [lon, lat]
    order per the GeoJSON spec).  Bounding-box columns (lat/lon_min/max) are
    auto-computed on insert for efficient spatial pre-filtering.
    """
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id", ondelete="SET NULL"), nullable=True)

    footprint_geojson = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False)
    cloud_cover_pct = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Bounding box for spatial pre-filtering
    lat_min = Column(Float, nullable=False, index=True)
    lat_max = Column(Float, nullable=False, index=True)
    lon_min = Column(Float, nullable=False, index=True)
    lon_max = Column(Float, nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    order = relationship("Order", back_populates="scenes")
    satellite = relationship("Satellite", back_populates="scenes")


class Order(Base):
    """A shooting order sent to (or planned for) a satellite."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tile_id = Column(Integer, ForeignKey("tiles.id"), nullable=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id"), nullable=True)

    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    target_name = Column(String(200), nullable=True)

    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)

    resolution_m = Column(Float, nullable=True)
    sensor_mode = Column(String(50), nullable=True)
    max_cloud_pct = Column(Float, nullable=False, default=20.0)
    sun_elev_min = Column(Float, nullable=True)
    off_nadir_max = Column(Float, nullable=True)

    priority = Column(Integer, nullable=False, default=5)

    # PLANNED | SCHEDULED | IN_PROGRESS | COMPLETED | FAILED | CANCELLED
    status = Column(String(20), nullable=False, default="PLANNED")

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    tile = relationship("Tile", back_populates="orders")
    satellite = relationship("Satellite", back_populates="orders")
    scenes = relationship("Scene", back_populates="order")
