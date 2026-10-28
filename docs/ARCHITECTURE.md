# Architecture

## Principles

1. **Measure before controlling.** Phase 1 watches the existing timer irrigation. Nothing waters automatically until the medium is characterized and the pilot baseline exists.
2. **Water limits live at the rack.** When control arrives (Phase 2), each rack's irrigation controller enforces hardwired limits: maximum valve-open time, a daily volume cap and a leak shutoff. A gateway crash, a WiFi drop or a bad recommendation can't flood a rack. The gateway sends setpoints within limits that plant science has approved, never raw valve commands.
3. **No invented biology.** No threshold or model assumes microbial populations, activity rates, nutrient-release rates or moisture limits that haven't been measured. EC is logged for research and never acted on.
4. **Trade secrets stay out.** The gateway knows a medium batch only by its ID.

```
 Cloud (later)       fleet view, crop recipes, analytics          Restricted DB (separate)
      ▲ outbound only                                                  formula, inoculation
 Site gateway        MQTT broker, storage, alerts, dashboard,   ◄── linked by batch ID only
                     crop-cycle records, cameras
      ▲ MQTT over the site's IoT WiFi
 Rack nodes          levels node: moisture, tray weight, medium temperature, rack air
                     water node:  valve feedback, flow, meter total, leaks, pump current
 Site climate node   room air temperature, RH, CO2, light
```

## Data flow

1. Nodes publish `agria/<site>/<node>/sensor/<id>/state` every 30 seconds. Binary sensors (valves, leaks) publish on change.
2. The `Hub` checks each reading against the sensor's plausible range, stores it, evaluates any configured thresholds and updates VPD and DLI.
3. The `IrrigationMonitor` tracks each level's valve and flow. Every open/close cycle becomes an `irrigation_events` row with its liters, taken from the meter total when available and from the flow integral otherwise. It raises delivery-fault alerts.
4. `Cycles` ties crop records to rack levels, so water per kg harvested comes from that level's irrigation events between sowing and harvest.
5. A maintenance thread runs stale-sensor, calibration and irrigation checks every 15 seconds and data retention daily.

## Alert types

| Kind | Raised when | Severity |
|---|---|---|
| `threshold` | A value stays outside configured limits for `delay_s` | per limit |
| `stale` | No reading for `stale_after_s` (not applied to binary sensors) | warn |
| `sensor_fault` | 3 implausible readings in 10 minutes | warn |
| `node_offline` | The broker delivers the node's last-will message | warn |
| `calibration` | A configured calibration interval has lapsed | warn |
| `valve_open_too_long` | A level's valve stays open past `max_open_s` | alarm |
| `no_flow` | A valve is open but no flow arrives within `no_flow_after_s` | warn |
| `flow_without_valve` | Flow above `leak_flow_lpm` with the valve shut for `flow_without_valve_s` | alarm |
| `daily_volume` | A level exceeds its optional `daily_volume_cap_l` | warn |

Default thresholds exist only for room climate, wide medium-temperature safety limits (5 °C and 35 °C), leak sensors and WiFi signal. Root-zone moisture has none until the medium specification provides them.

## Storage

The gateway uses SQLite in WAL mode. The pilot (about 77 sensors at 30 s) writes roughly 220,000 rows a day. Raw data is kept 365 days, because the trial data trains the Phase 4 models, and then rolled up hourly. Move to TimescaleDB at Phase 3 scale-out; all access goes through `store.py`. Run the gateway on an SSD.

## Security

- The broker requires a password, and nodes and the gateway use separate credentials.
- Writes (acknowledging alerts, cycles, harvests, calibrations, batches) require `AGRIA_API_TOKEN`.
- Use an isolated IoT network and VPN-only remote access. Don't port-forward the dashboard.
- Before Phase 2 control: TLS on MQTT, per-node credentials, per-user authentication.
