# Architecture

## Principle: supervision is separate from control

The system has three tiers. Each tier keeps the crop safe if the tier above it fails.

```
 Cloud (later)          fleet dashboard, recipes, analytics, OTA, remote access
      ▲  outbound only; never in the real-time path
 Site gateway           this repo: MQTT broker, storage, alerting, dashboard, cameras
      ▲  MQTT over the site's IoT WiFi
 Edge nodes             ESP32 + ESPHome sensor nodes (Phase 1)
                        PLC / industrial controller for actuators (Phase 2+)
```

**Edge.** In Phase 1, the edge nodes only measure. When control arrives, the controller that drives heaters, fans, pumps and dosing runs its loops locally. Hard limits are enforced in its firmware and wiring: maximum pump runtime per cycle, pH and EC cutoffs, float-switch interlocks and over-temperature shutdown. Losing the gateway or the WiFi must leave the room in a safe state. The gateway sends setpoints, such as "VPD 1.0 kPa" or "EC 1.8". It never sends raw relay commands.

**Gateway.** The gateway is a small Linux machine at each site running `docker compose`. All components talk over MQTT, so cameras, future control logic and robots join the system as additional publishers and subscribers instead of requiring rewrites.

**Cloud.** The cloud tier is deferred until there is more than one site to manage. When it arrives, the gateway pushes data outbound (MQTT bridge or HTTPS). No inbound ports are opened on a site network.

## Data flow

1. A node publishes `agria/<site>/<node>/sensor/<id>/state` every 30 seconds. The broker publishes `.../status = offline` (the node's last-will message) if the node drops.
2. The `Hub` maps the topic to a configured sensor, checks the value against the sensor's plausible range, stores it, evaluates thresholds and updates derived metrics (VPD and DLI).
3. The `AlertManager` keeps one active alert per sensor and alert type, persists it and hands it to the `Notifier`, which sends on its own thread so a slow endpoint can't stall ingest.
4. A maintenance thread runs stale and calibration checks every 15 seconds and data retention daily.

## Alert types

| Kind | Raised when | Clears when |
|---|---|---|
| `threshold` | The value stays outside the warning or alarm limits for `delay_s` (default 2 min) | The value returns inside the limits by `hysteresis` |
| `stale` | No valid reading for `stale_after_s` (default 5 min) | The next valid reading arrives |
| `sensor_fault` | 3 implausible readings in 10 minutes. Readings outside the physical range, or NaN, are dropped and not stored. | 10 minutes pass without an implausible reading |
| `node_offline` | The broker delivers the node's last-will message | The node republishes `online` |
| `calibration` | No calibration has been logged, or the calibration interval has passed | A calibration is logged |

Redundant alerts are suppressed. A sensor isn't also flagged stale while its node is offline or while it has an active fault alert.

## Storage

The gateway uses SQLite in WAL mode. At this scale (about 30 sensors at 30-second intervals, roughly 90,000 rows a day) it has plenty of headroom. Raw readings are kept 90 days and then rolled up to hourly mean, min and max values that are kept indefinitely. All access goes through `store.py`, so moving to TimescaleDB when the fleet grows is a contained change.

**Run the gateway on an SSD, not an SD card.** Continuous database writes wear out SD cards within months.

## Security posture (Phase 1)

- The MQTT broker requires a password. Nodes and the gateway use separate credentials.
- Writes to the dashboard (acknowledging alerts, logging calibrations) require `AGRIA_API_TOKEN`. Reads are open to the local network.
- Put the nodes and the gateway on a dedicated IoT WiFi network or VLAN, isolated from office and guest traffic.
- Don't port-forward the dashboard. Use a VPN (Tailscale or WireGuard) for remote access.
- Before customer deployments or any actuator control: add TLS on MQTT, per-node credentials and per-user authentication on the dashboard.
