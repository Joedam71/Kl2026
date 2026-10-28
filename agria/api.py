"""HTTP API and dashboard."""

from __future__ import annotations

import csv
import io
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cycles import INTERVENTION_KINDS, IRRIGATION_MODES, STAGES, CycleError

STATIC = Path(__file__).parent / "static"


class AckIn(BaseModel):
    by: str


class CalibrationIn(BaseModel):
    sensor_key: str
    by: str | None = None
    notes: str | None = None


class BatchIn(BaseModel):
    # An opaque identifier only. Formulation and inoculation details belong
    # in the restricted system, never here.
    id: str = Field(min_length=1, max_length=64)
    received_ts: float | None = None
    notes: str | None = Field(default=None, max_length=1000)
    by: str | None = None


class CycleIn(BaseModel):
    site: str
    rack: str
    level: int
    variety: str = Field(min_length=1, max_length=100)
    irrigation_mode: str
    batch_id: str | None = None
    inoculation_ts: float | None = None
    notes: str | None = None
    by: str | None = None


class StageIn(BaseModel):
    stage: str
    by: str | None = None


class InterventionIn(BaseModel):
    kind: str
    notes: str | None = None
    by: str | None = None


class HarvestIn(BaseModel):
    yield_g: float
    notes: str | None = None
    by: str | None = None


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

    # irrigation

    @app.get("/api/irrigation/events")
    def irrigation_events(site: str | None = None, zone: str | None = None,
                          hours: float = Query(24, gt=0, le=24 * 400), limit: int = Query(500, le=5000)):
        return gw.store.irrigation_events(site=site, zone=zone, since=time.time() - hours * 3600, limit=limit)

    # medium batches and crop cycles

    @app.get("/api/meta")
    def meta():
        return {"irrigation_modes": IRRIGATION_MODES, "stages": STAGES, "intervention_kinds": INTERVENTION_KINDS}

    @app.get("/api/batches")
    def batches():
        return gw.store.batches()

    @app.post("/api/batches", dependencies=[Depends(require_token)])
    def add_batch(body: BatchIn):
        if gw.store.batch(body.id):
            raise HTTPException(409, f"batch {body.id} already exists")
        gw.store.add_batch(body.id, body.received_ts, body.notes, body.by, time.time())
        return {"id": body.id}

    def cycle_call(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except CycleError as e:
            raise HTTPException(409 if "already" in str(e) else 400, str(e)) from None

    @app.get("/api/cycles")
    def cycles(site: str | None = None, active: bool | None = None):
        return [gw.cycles.view(c) for c in gw.store.cycles(site=site, active=active)]

    @app.get("/api/cycles/{cycle_id}")
    def cycle(cycle_id: int):
        c = gw.store.cycle(cycle_id)
        if not c:
            raise HTTPException(404, "cycle not found")
        return gw.cycles.view(c)

    @app.post("/api/cycles", dependencies=[Depends(require_token)])
    def start_cycle(body: CycleIn):
        return {"id": cycle_call(gw.cycles.start, **body.model_dump())}

    @app.post("/api/cycles/{cycle_id}/stage", dependencies=[Depends(require_token)])
    def set_stage(cycle_id: int, body: StageIn):
        cycle_call(gw.cycles.set_stage, cycle_id, body.stage, body.by)
        return {"ok": True}

    @app.post("/api/cycles/{cycle_id}/interventions", dependencies=[Depends(require_token)])
    def log_intervention(cycle_id: int, body: InterventionIn):
        return {"id": cycle_call(gw.cycles.log, cycle_id, body.kind, body.notes, body.by)}

    @app.post("/api/cycles/{cycle_id}/harvest", dependencies=[Depends(require_token)])
    def harvest(cycle_id: int, body: HarvestIn):
        cycle_call(gw.cycles.harvest, cycle_id, body.yield_g, body.by, body.notes)
        return {"ok": True}

    @app.get("/api/trial/summary")
    def trial_summary(site: str | None = None):
        """Completed cycles by variety and irrigation arm (timer vs sensor-guided)."""
        return gw.cycles.trial_summary(site)

    # export for the plant-science team and offline analysis

    @app.get("/api/export.csv")
    def export(site: str, rack: str | None = None, hours: float = Query(168, gt=0, le=24 * 400)):
        keys = [s.key for s in gw.cfg.site_sensors(site) if rack is None or s.rack == rack]
        if not keys:
            raise HTTPException(404, "no sensors match")
        end = time.time()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["timestamp_utc", "sensor_key", "kind", "rack", "level", "value", "unit"])
        for r in gw.store.raw_readings(keys, end - hours * 3600, end):
            s = gw.cfg.sensors[r["sensor_key"]]
            w.writerow([datetime.fromtimestamp(r["ts"], timezone.utc).isoformat(timespec="seconds"),
                        s.key, s.kind, s.rack or "", s.level or "", r["value"], s.unit])
        name = f"agria-{site}{'-' + rack if rack else ''}-{int(hours)}h.csv"
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

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
