# Agria site gateway

Monitoring, alerting and camera capture for Agria greenhouses and containers. This is **Phase 1** of the roadmap: the system watches and warns, and it does not control anything. Control comes in later phases, once the sensors have proven reliable and the hardware safety limits are in place (see [docs/ROADMAP.md](docs/ROADMAP.md)).

The first deployment covers one greenhouse and one container, both on WiFi with water and power available.

## What it does

- Collects air temperature, humidity, CO2, light (PPFD), water temperature, pH, EC, dissolved oxygen, reservoir level, a low-level float switch and node WiFi strength from ESPHome sensor nodes over MQTT.
- Computes vapor pressure deficit (VPD) and daily light integral (DLI).
- Raises alerts for out-of-range values, stale sensors, faulty probes, offline nodes and overdue probe calibrations. Alerts are debounced and use hysteresis, so they don't flap, and they push to a phone through ntfy or to any webhook.
- Tracks probe calibration and records who performed each one and when.
- Captures scheduled still images from cameras, building the time-lapse record and the future training set for vision models.
- Serves a dashboard on port 8080 for the local network.
- Includes a simulator, so the whole system can run before any hardware is bought.

## Quick start (no hardware)

```sh
./deploy/setup.sh                      # creates .env with random secrets and broker passwords
docker compose --profile sim up -d     # broker + gateway + simulator
open http://localhost:8080
```

To develop without Docker, you need a local MQTT broker (`mosquitto`):

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
AGRIA_MQTT_HOST=localhost .venv/bin/agria
.venv/bin/agria-sim --speed 60 --fault container-1/c1-nutrient/ph=drift
```

## Layout

| Path | What |
|---|---|
| `agria/` | Gateway service: MQTT ingest (`hub.py`), alerting (`alerts.py`), storage (`store.py`), API and dashboard (`api.py`, `static/`), cameras, notifications, simulator |
| `config/sites.yaml` | Sites, nodes, sensors, thresholds, cameras and notification targets. This is the one file to edit per site. |
| `firmware/esphome/` | Sensor-node firmware configs, one file per node |
| `deploy/` | Broker config and first-time setup |
| `docs/` | Architecture, hardware bill of materials, roadmap, MQTT contract |

## Commissioning a real node

1. Copy `firmware/esphome/secrets.yaml.example` to `secrets.yaml` and fill it in.
2. Flash the node with `esphome run greenhouse-1-climate.yaml`.
3. Open `/api/unmapped` on the gateway. Any topic that appears there is a sensor the node publishes that `sites.yaml` doesn't know about yet.
4. Calibrate the pH, EC and DO probes, then log each calibration from the dashboard (click the sensor tile). Until a calibration is logged, the dashboard shows a "no calibration on record" warning for that probe.

## Default thresholds

The defaults assume leafy greens and herbs grown hydroponically. **Set the real crop's ranges in `sites.yaml` before relying on the alerts.** The CO2 alarm at 5,000 ppm is a human-safety limit (the OSHA 8-hour exposure limit), not a plant limit, and it matters in a sealed container with CO2 enrichment.
