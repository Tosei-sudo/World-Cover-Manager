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


# ── Satellite ─────────────────────────────────────────────────────────────────

class SatelliteBase(BaseModel):
    name: str
    norad_id: Optional[int] = None
    tle_line1: str = Field(..., min_length=69, max_length=100)
    tle_line2: str = Field(..., min_length=69, max_length=100)
    swath_width_km: float = Field(..., gt=0)
    sensor_modes: Optional[str] = None   # comma-separated, e.g. "MULTISPECTRAL,PANCHROMATIC"
    min_resolution_m: Optional[float] = Field(None, gt=0)
    is_active: bool = True
    notes: Optional[str] = None


class SatelliteCreate(SatelliteBase):
    pass


class SatellitePatch(BaseModel):
    name: Optional[str] = None
    norad_id: Optional[int] = None
    tle_line1: Optional[str] = None
    tle_line2: Optional[str] = None
    swath_width_km: Optional[float] = None
    sensor_modes: Optional[str] = None
    min_resolution_m: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class SatelliteOut(SatelliteBase):
    id: int
    tle_epoch: Optional[datetime] = None
    tle_updated_at: datetime
    created_at: datetime
    tile_coverage_warning: Optional[str] = None
    model_config = {"from_attributes": True, "populate_by_name": True}


# ── OrbitalPass ───────────────────────────────────────────────────────────────

class OrbitalPassOut(BaseModel):
    id: int
    satellite_id: int
    tile_id: int
    pass_start: datetime
    pass_end: datetime
    duration_s: int
    computed_at: datetime
    model_config = {"from_attributes": True}


class PassOpportunity(BaseModel):
    """One upcoming imaging opportunity: a specific (satellite, tile, pass) combo."""
    tile: TileOut
    satellite: SatelliteOut
    pass_start: datetime
    pass_end: datetime
    duration_s: int


class ComputePassesResult(BaseModel):
    satellite_id: int
    window_hours: int
    tiles_checked: int
    passes_found: int
    elapsed_s: float


class PassStatus(BaseModel):
    satellite_id: int
    passes_valid_until: Optional[datetime] = None
    needs_recompute: bool
    pass_count: int


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderBase(BaseModel):
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    target_name: Optional[str] = None
    tile_id: Optional[int] = None
    satellite_id: Optional[int] = None
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
    satellite_id: Optional[int] = None
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
