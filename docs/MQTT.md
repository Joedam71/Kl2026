# MQTT contract

The root topic is `agria/`. Site and node IDs match `config/sites.yaml`. The layout below matches what ESPHome produces with `topic_prefix: agria/<site>/<node>`, so the nodes need no custom firmware.

## Telemetry (Phase 1)

| Topic | Payload | Notes |
|---|---|---|
| `agria/<site>/<node>/sensor/<sensor>/state` | Number as text, e.g. `5.82` | `nan` and out-of-range values are treated as implausible |
| `agria/<site>/<node>/binary_sensor/<sensor>/state` | `ON` / `OFF` | Stored as 1 / 0 |
| `agria/<site>/<node>/status` | `online` / `offline` | Retained. `offline` is the node's last will and testament. |

The gateway timestamps each reading on receipt. Topics that don't match a configured sensor are listed at `GET /api/unmapped`.

## Reserved for Phase 2+ (control)

These topics are not implemented yet. They are defined now so that later control and robotics work fits into the same structure.

| Topic | Direction | Payload |
|---|---|---|
| `agria/<site>/<node>/cmd/<target>` | gateway → controller | JSON `{"id": "<uuid>", "setpoint": 1.0, "source": "user:joe", "expires": <ts>}` |
| `agria/<site>/<node>/ack/<target>` | controller → gateway | JSON `{"id": "<uuid>", "accepted": true, "reason": null}` |
| `agria/<site>/<node>/actuator/<target>/state` | controller → gateway | Actual output state (relay on/off, duty cycle, dosing pulses) |

Rules for control:

- Commands are setpoints and modes, never raw relay toggles.
- Every command carries an ID and an expiry. When a command expires, the controller falls back to its local default.
- The controller can reject a command, for example when it falls outside the controller's hard limits, and must say why in the acknowledgement.
- Robots (Phase 5) use the same command, acknowledgement and state pattern through the ROS 2 MQTT bridge.
