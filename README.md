# AGRIA site gateway

Monitoring, irrigation-delivery tracking, crop-cycle records and alerting for AGRIA racks in the greenhouse and container.

AGRIA grows in a **biologically active, soil-based medium** about 2 inches deep on six-level racks. It is not hydroponic. The system therefore centers on root-zone moisture, the water actually delivered to each level, and crop outcomes. It does not dose nutrients, and it never acts on EC readings.

This is **Phase 1**: measure and record. The gateway controls nothing. Irrigation control comes in Phase 2, and only after the Growing Medium Characterization Specification is approved and the pilot rack's baseline data is in (see [docs/ROADMAP.md](docs/ROADMAP.md)).

## What it does

- **Root zone, per rack level:** two moisture sensors (raw millivolts plus VWC), reference-tray weight on load cells, and medium temperature.
- **Water delivery, per level:** valve-position feedback, flow rate and meter total. Every watering becomes an event with its liters and duration. The gateway alerts on a valve stuck open, an open valve with no flow, water flowing while the valve is shut, and an optional daily volume cap.
- **Rack and room conditions:** leak sensors, supply-pump current, air temperature and RH at the top and bottom of the rack, plus room CO2 and light. VPD and DLI are computed.
- **Crop-cycle records:** one record per level per crop, holding the medium batch ID, inoculation date, variety, growth stages, interventions, harvest weight and irrigation arm (timer or sensor). From these the gateway computes **liters of water per kg harvested**, and the trial summary compares the timer and sensor arms.
- **Calibration log:** records each moisture-sensor calibration against tray weight, with who did it, when and how.
- **CSV export:** per rack, for the plant-science team.
- **Alerts:** phone push (ntfy) or webhook, debounced so a value hovering at a limit doesn't page repeatedly.
- **Simulator:** generates data for the rack with injectable faults, so the whole system runs before hardware arrives.

**Moisture sensors have no alert thresholds by default, and that's deliberate.** The medium's field capacity and dry-down rate haven't been measured. Limits are added to `config/sites.yaml` from the approved medium specification, not invented.

## Quick start (no hardware)

```sh
./deploy/setup.sh                      # creates .env with random secrets and broker passwords
docker compose --profile sim up -d     # broker + gateway + simulator
open http://localhost:8080
```

Without Docker (needs a local `mosquitto`):

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
AGRIA_MQTT_HOST=localhost .venv/bin/agria
.venv/bin/agria-sim --speed 120 --fault container-1/rack-a-l5=leak
```

## Layout

| Path | What |
|---|---|
| `agria/hub.py` | Ingest, plausibility checks, thresholds, derived metrics, rack views |
| `agria/irrigation.py` | Watering events and water-delivery fault detection |
| `agria/cycles.py` | Crop cycles, interventions, harvest, water per kg, trial summary |
| `agria/store.py` | SQLite storage |
| `agria/api.py`, `agria/static/` | HTTP API and dashboard |
| `config/sites.yaml` | Sites, racks, nodes, sensors, limits, notification targets |
| `firmware/esphome/` | Node firmware: site climate, rack levels, rack water |
| `docs/` | Architecture, data model, pilot trial protocol, hardware, roadmap, MQTT contract |

## Data handling

The medium formulation and inoculation know-how are trade secrets. This system stores **batch IDs only** and has no fields for formulation data. That data stays in a separate restricted system. See [docs/DATA_MODEL.md](docs/DATA_MODEL.md).
