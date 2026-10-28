from pathlib import Path

from fastapi.testclient import TestClient

from agria.api import create_app
from agria.main import Gateway, Settings

SITE = "container-1"


def make(tmp_path: Path, token=None):
    gw = Gateway(Settings(data_dir=str(tmp_path), mqtt_host=None, api_token=token))
    return gw, TestClient(create_app(gw))


def test_read_endpoints(tmp_path):
    gw, c = make(tmp_path)
    with c:
        gw.hub.handle_message(f"agria/{SITE}/rack-a-levels/sensor/l1_weight/state", b"27.5")
        assert c.get("/api/health").json()["ok"]
        site = c.get("/api/sites").json()[0]
        assert site["racks"][0]["id"] == "rack-a"
        assert all(s["rack"] is None for s in site["sensors"])
        assert c.get(f"/api/readings/{SITE}/rack-a-levels/l1_weight?hours=1").json()["points"]
        csv = c.get(f"/api/export.csv?site={SITE}&rack=rack-a&hours=1")
        assert csv.status_code == 200 and "l1_weight" in csv.text and csv.text.startswith("timestamp_utc")
        assert c.get("/api/meta").json()["irrigation_modes"] == ["timer", "sensor", "manual"]
        assert c.get("/").status_code == 200


def test_cycle_endpoints(tmp_path):
    gw, c = make(tmp_path)
    with c:
        assert c.post("/api/batches", json={"id": "B-001", "by": "Joe"}).status_code == 200
        assert c.post("/api/batches", json={"id": "B-001"}).status_code == 409
        body = {"site": SITE, "rack": "rack-a", "level": 4, "variety": "mizuna",
                "irrigation_mode": "sensor", "batch_id": "B-001", "by": "Joe"}
        cid = c.post("/api/cycles", json=body).json()["id"]
        assert c.post("/api/cycles", json=body).status_code == 409
        assert c.post(f"/api/cycles/{cid}/stage", json={"stage": "germination"}).status_code == 200
        assert c.post(f"/api/cycles/{cid}/stage", json={"stage": "bogus"}).status_code == 400
        assert c.post(f"/api/cycles/{cid}/interventions", json={"kind": "observation", "notes": "ok"}).status_code == 200
        lvl4 = next(l for l in c.get("/api/sites").json()[0]["racks"][0]["levels"] if l["level"] == 4)
        assert lvl4["cycle"]["variety"] == "mizuna"
        assert c.post(f"/api/cycles/{cid}/harvest", json={"yield_g": 1800}).status_code == 200
        assert c.get(f"/api/cycles/{cid}").json()["yield_g"] == 1800
        assert c.get(f"/api/trial/summary?site={SITE}").json()[0]["cycles"] == 1


def test_write_token(tmp_path):
    gw, c = make(tmp_path, token="s3cret")
    with c:
        assert c.post("/api/batches", json={"id": "B-9"}).status_code == 401
        ok = c.post("/api/batches", json={"id": "B-9"}, headers={"Authorization": "Bearer s3cret"})
        assert ok.status_code == 200
