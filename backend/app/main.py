from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .database import Base, engine
from .routers import orders, passes, satellites, scenes, stats, tiles

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="World Cover Manager",
    description="Satellite global land coverage planning and progress tracker",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tiles.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(satellites.router, prefix="/api")
app.include_router(passes.router, prefix="/api")
app.include_router(scenes.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/docs", include_in_schema=False)
async def swagger_ui() -> HTMLResponse:
    return HTMLResponse("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>World Cover Manager – API Docs</title>
  <link rel="stylesheet" href="/vendor/swagger-ui/swagger-ui.css" />
  <style>
    body { margin: 0; }
    .topbar { background: #1a2332 !important; }
    .topbar-wrapper .link { display: none; }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="/vendor/swagger-ui/swagger-ui-bundle.js"></script>
<script src="/vendor/swagger-ui/swagger-ui-standalone-preset.js"></script>
<script>
  SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    layout: "StandaloneLayout",
    deepLinking: true,
    defaultModelsExpandDepth: 1,
    defaultModelExpandDepth: 2,
    displayRequestDuration: true,
    filter: true,
  });
</script>
</body>
</html>""")


# Serve frontend from the sibling "frontend" directory
_frontend = Path(__file__).parent.parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
