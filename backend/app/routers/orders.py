from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Order, Tile
from ..schemas import OrderCreate, OrderOut, OrderPatch

router = APIRouter(prefix="/orders", tags=["orders"])

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


@router.get("", response_model=list[OrderOut])
def list_orders(
    status: Optional[str] = Query(None),
    tile_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Order)
    if status:
        q = q.filter(Order.status == status)
    if tile_id is not None:
        q = q.filter(Order.tile_id == tile_id)
    return q.order_by(Order.created_at.desc()).all()


@router.post("", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = Order(**body.model_dump())
    db.add(order)
    # Mark parent tile as IN_PROGRESS when a new order targets it
    if body.tile_id:
        tile = db.get(Tile, body.tile_id)
        if tile and tile.status == "NOT_STARTED":
            tile.status = "IN_PROGRESS"
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderOut)
def patch_order(order_id: int, body: OrderPatch, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = body.model_dump(exclude_unset=True)
    new_status = updates.get("status")

    # Auto-set completed_at when transitioning to a terminal status
    if new_status in TERMINAL_STATUSES and not order.completed_at:
        updates.setdefault("completed_at", datetime.utcnow())

    for field, value in updates.items():
        setattr(order, field, value)

    # Propagate COMPLETED status to the tile
    if new_status == "COMPLETED" and order.tile_id:
        tile = db.get(Tile, order.tile_id)
        if tile:
            tile.status = "COMPLETED"
            tile.coverage_count = tile.coverage_count + 1
            tile.last_captured_at = datetime.utcnow()

    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
