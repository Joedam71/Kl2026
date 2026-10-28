"""HTTP API and dashboard."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

STATIC = Path(__file__).parent / "static"


class AckIn(BaseModel):
    by: str


class CalibrationIn(BaseModel):
    sensor_key: str
    by: str | None = None
    notes: str | None = None


def create_app(gw) -> FastAPI:
    """``gw`` is an agria.main.Gateway (or anything with the same attributes)."""

    @asynccontextmanager
    async def lifespan(app):
        gw.start()
        try:
            yield
        finally:
            gw.stop()

    app = FastAPI(title="Agria Gateway", version="0.1.0", lifespan=lifespan)

    def require_token(authorization: str | None = Header(default=None)):
        # Write endpoints need the token when AGRIA_API_TOKEN is set.
        if gw.settings.api_token and authorization != f"Bearer {gw.settings.api_token}":
            raise HTTPException(401, "missing or bad API token")

    @app.get("/api/health")
    def health():
        return {"ok": True, "mqtt_connected": bool(gw.mqtt and gw.mqtt.connected),
                "uptime_s": round(time.time() - gw.hub.started), "write_token_required": bool(gw.settings.api_token)}

    @app.get("/api/sites")
    def sites():
        return gw.hub.snapshot()

    @app.get("/api/readings/{site}/{node}/{sensor}")
    def readings(site: str, node: str, sensor: str, hours: float = Query(24, gt=0, le=24 * 400),
                 points: int = Query(300, ge=10, le=5000)):
        key = f"{site}/{node}/{sensor}"
        if key not in gw.cfg.sensors:
            raise HTTPException(404, f"unknown sensor {key}")
        end = time.time()
        return {"key": key, "points": gw.store.history(key, end - hours * 3600, end, points)}

    @app.get("/api/alerts")
    def alerts(active: bool = False, limit: int = Query(200, le=2000)):
        return gw.store.alerts(active_only=active, limit=limit)

    @app.post("/api/alerts/{alert_id}/ack", dependencies=[Depends(require_token)])
    def ack(alert_id: int, body: AckIn):
        if not gw.store.ack_alert(alert_id, body.by, time.time()):
            raise HTTPException(404, "alert not found or already acknowledged")
        return {"ok": True}

    @app.get("/api/calibrations")
    def calibrations(sensor_key: str | None = None):
        return gw.store.calibrations(sensor_key)

    @app.post("/api/calibrations", dependencies=[Depends(require_token)])
    def add_calibration(body: CalibrationIn):
        if body.sensor_key not in gw.cfg.sensors:
            raise HTTPException(404, f"unknown sensor {body.sensor_key}")
        return {"id": gw.hub.record_calibration(body.sensor_key, body.by, body.notes)}

    @app.get("/api/unmapped")
    def unmapped():
        """MQTT topics seen but not in sites.yaml. Useful while commissioning nodes."""
        return sorted(gw.hub.unmapped.values(), key=lambda u: u["topic"])

    @app.get("/api/cameras/{site}/{camera}/latest")
    def camera_latest(site: str, camera: str):
        img = gw.store.latest_image(site, camera)
        if not img:
            raise HTTPException(404, "no image captured yet")
        path = (gw.image_dir / img["path"]).resolve()
        if not path.is_relative_to(gw.image_dir.resolve()) or not path.exists():
            raise HTTPException(404, "image file missing")
        return FileResponse(path, media_type="image/jpeg", headers={"X-Captured-At": str(img["ts"])})

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
