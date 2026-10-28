from pathlib import Path

from fastapi.testclient import TestClient

from agria.api import create_app
from agria.main import Gateway, Settings


def make(tmp_path: Path, token=None):
    gw = Gateway(Settings(data_dir=str(tmp_path), mqtt_host=None, api_token=token))
    return gw, TestClient(create_app(gw))


def test_endpoints(tmp_path):
    gw, c = make(tmp_path)
    with c:
        gw.hub.handle_message("agria/container-1/c1-nutrient/sensor/ph/state", b"5.9")
        assert c.get("/api/health").json()["ok"]
        sites = c.get("/api/sites").json()
        ph = next(s for s in sites[1]["sensors"] if s["id"] == "ph")
        assert ph["value"] == 5.9 and ph["calibration"]["interval_days"] == 30
        assert c.get("/api/readings/container-1/c1-nutrient/ph?hours=1").json()["points"]
        assert c.get("/api/readings/nope/x/y").status_code == 404
        r = c.post("/api/calibrations", json={"sensor_key": "container-1/c1-nutrient/ph", "by": "Joe"})
        assert r.status_code == 200
        assert c.get("/").status_code == 200
        assert c.get("/api/cameras/greenhouse-1/none/latest").status_code == 404


def test_write_token(tmp_path):
    gw, c = make(tmp_path, token="s3cret")
    with c:
        body = {"sensor_key": "container-1/c1-nutrient/ph"}
        assert c.post("/api/calibrations", json=body).status_code == 401
        ok = c.post("/api/calibrations", json=body, headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
