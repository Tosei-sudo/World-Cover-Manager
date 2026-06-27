from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Tile
from ..schemas import TileOut, TilePatch

router = APIRouter(prefix="/tiles", tags=["tiles"])


@router.get("", response_model=list[TileOut])
def list_tiles(
    is_land: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Tile)
    if is_land is not None:
        q = q.filter(Tile.is_land == is_land)
    if status:
        q = q.filter(Tile.status == status)
    return q.order_by(Tile.id).all()


@router.get("/{tile_id}", response_model=TileOut)
def get_tile(tile_id: int, db: Session = Depends(get_db)):
    tile = db.get(Tile, tile_id)
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")
    return tile


@router.patch("/{tile_id}", response_model=TileOut)
def patch_tile(tile_id: int, body: TilePatch, db: Session = Depends(get_db)):
    tile = db.get(Tile, tile_id)
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tile, field, value)
    db.commit()
    db.refresh(tile)
    return tile
