from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .database import Base, engine
from .routers import orders, stats, tiles

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="World Cover Manager",
    description="Satellite global land coverage planning and progress tracker",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tiles.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(stats.router, prefix="/api")

# Serve frontend from the sibling "frontend" directory
_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
