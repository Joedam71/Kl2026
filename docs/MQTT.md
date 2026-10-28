# MQTT contract

The root topic is `agria/`. Site and node IDs match `config/sites.yaml`. The layout matches ESPHome's `topic_prefix: agria/<site>/<node>`, so the nodes need no custom firmware.

## Telemetry (Phase 1)

| Topic | Payload | Notes |
|---|---|---|
| `agria/<site>/<node>/sensor/<sensor>/state` | Number as text | `nan` and out-of-range values are dropped and counted as implausible |
| `agria/<site>/<node>/binary_sensor/<sensor>/state` | `ON` / `OFF` | Valves and leaks; published on change |
| `agria/<site>/<node>/status` | `online` / `offline` | Retained; `offline` is the node's last will |

## Rack sensor naming

Rack sensors carry the level in their ID, so the gateway can map them to rack levels and irrigation zones:

| Node | Sensor IDs per level N |
|---|---|
| `<rack>-levels` | `lN_moisture_a`, `lN_moisture_b` (% VWC), `lN_moisture_a_mv`, `lN_moisture_b_mv` (raw), `lN_weight` (kg), `lN_medium_temp` (°C) |
| `<rack>-water` | `lN_valve` (binary feedback), `lN_flow` (L/min), `lN_volume` (L, cumulative) |

Rack-wide: `leak_floor`, `leak_supply` (binary), `pump_current` (A), `air_temp_top`, `rh_top`, `air_temp_bottom`, `rh_bottom`.

The gateway timestamps on receipt. Topics that don't match the config are listed at `GET /api/unmapped`.

## Reserved for Phase 2 (irrigation control)

Not implemented yet. The topics are defined now so control fits the same structure.

| Topic | Direction | Payload |
|---|---|---|
| `agria/<site>/<rack>-water/cmd/lN` | gateway → controller | JSON `{"id": "<uuid>", "mode": "sensor", "lower_vwc": <approved>, "upper_vwc": <approved>, "pulse_l": 1.5, "source": "user:joe", "expires": <ts>}` |
| `agria/<site>/<rack>-water/ack/lN` | controller → gateway | JSON `{"id": "<uuid>", "accepted": true, "reason": null}` |

The controller enforces its own hard limits regardless of any command, falls back to its local default when a command expires, and rejects out-of-limit commands with a reason.
