from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Tile ──────────────────────────────────────────────────────────────────────

class TileBase(BaseModel):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    center_lat: float
    center_lon: float
    tile_size: float = 10.0
    is_land: bool = True
    status: str = "NOT_STARTED"
    coverage_count: int = 0
    last_captured_at: Optional[datetime] = None
    notes: Optional[str] = None


class TileCreate(TileBase):
    pass


class TilePatch(BaseModel):
    status: Optional[str] = None
    is_land: Optional[bool] = None
    coverage_count: Optional[int] = None
    last_captured_at: Optional[datetime] = None
    notes: Optional[str] = None


class TileOut(TileBase):
    id: int

    model_config = {"from_attributes": True}


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderBase(BaseModel):
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    target_name: Optional[str] = None
    tile_id: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    resolution_m: Optional[float] = Field(None, gt=0)
    sensor_mode: Optional[str] = None
    max_cloud_pct: float = Field(20.0, ge=0, le=100)
    sun_elev_min: Optional[float] = Field(None, ge=0, le=90)
    off_nadir_max: Optional[float] = Field(None, ge=0, le=60)
    priority: int = Field(5, ge=1, le=10)
    notes: Optional[str] = None


class OrderCreate(OrderBase):
    pass


class OrderPatch(BaseModel):
    target_name: Optional[str] = None
    tile_id: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    resolution_m: Optional[float] = None
    sensor_mode: Optional[str] = None
    max_cloud_pct: Optional[float] = None
    sun_elev_min: Optional[float] = None
    off_nadir_max: Optional[float] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class OrderOut(OrderBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

class CoverageStats(BaseModel):
    total_land_tiles: int
    completed_tiles: int
    in_progress_tiles: int
    not_started_tiles: int
    coverage_pct: float
    total_orders: int
    orders_by_status: dict[str, int]
