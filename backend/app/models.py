from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import relationship
from .database import Base


class Tile(Base):
    """One cell in the global lat/lon grid. Only land tiles need coverage."""
    __tablename__ = "tiles"

    id = Column(Integer, primary_key=True, index=True)
    # Grid cell boundaries (degrees)
    lat_min = Column(Float, nullable=False)
    lat_max = Column(Float, nullable=False)
    lon_min = Column(Float, nullable=False)
    lon_max = Column(Float, nullable=False)
    # Derived centre point (stored for quick access)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    # Size in degrees (e.g. 10.0 for a 10°×10° tile)
    tile_size = Column(Float, nullable=False, default=10.0)

    is_land = Column(Boolean, nullable=False, default=True)
    # NOT_STARTED | IN_PROGRESS | COMPLETED
    status = Column(String(20), nullable=False, default="NOT_STARTED")
    coverage_count = Column(Integer, nullable=False, default=0)
    last_captured_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    orders = relationship("Order", back_populates="tile")


class Order(Base):
    """A shooting order sent to (or planned for) the satellite."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tile_id = Column(Integer, ForeignKey("tiles.id"), nullable=True)

    # Target centre
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    target_name = Column(String(200), nullable=True)

    # Schedule window
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)

    # Shooting parameters
    resolution_m = Column(Float, nullable=True)       # Ground resolution (m)
    sensor_mode = Column(String(50), nullable=True)   # MULTISPECTRAL | PANCHROMATIC | SAR …
    max_cloud_pct = Column(Float, nullable=False, default=20.0)
    sun_elev_min = Column(Float, nullable=True)       # Min sun elevation angle (°)
    off_nadir_max = Column(Float, nullable=True)      # Max off-nadir angle (°)

    priority = Column(Integer, nullable=False, default=5)  # 1 (low) – 10 (high)

    # PLANNED | SCHEDULED | IN_PROGRESS | COMPLETED | FAILED | CANCELLED
    status = Column(String(20), nullable=False, default="PLANNED")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    tile = relationship("Tile", back_populates="orders")
