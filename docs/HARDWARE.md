# Phase 1 hardware: pilot rack

One six-level AGRIA rack (8 ft × 8 ft × 4 ft, 192 sq ft of growing area, about 2 in of medium), plus site climate. Prices are late-2026 estimates; re-quote before ordering. This bill of materials matches the build proposal.

## Pilot rack

| Item | Qty | Unit (est.) | Notes |
|---|---|---|---|
| Shallow medium-moisture sensors | 12 | $150–350 | 2 per level. Evaluate 2–3 types (e.g. METER TEROS 10 class). Insert horizontally at mid-depth; the medium is only 2 in deep. |
| Load cells + HX711 amplifier, reference tray per level | 6 sets | $250–600 | 4 cells under a removable reference tray. This is the ground truth the moisture sensors are calibrated against. |
| DS18B20 waterproof probes | 6 | $10–30 | Medium temperature, mid-depth |
| Solenoid valve with position feedback + hall-effect flow meter, per level | 6 | $120–300 | Feedback must report actual valve position, not the command. Flow meter inputs need external 10 kΩ pull-ups (ESP32 GPIO34–39). |
| Leak sensors (rope or spot, dry contact) | 2–4 | $25–60 | Under the rack and at the supply manifold |
| Current transformer (SCT-013) + ADS1115 | 1 | $30–60 | Supply-pump current |
| SHT45 temp/RH, one -AD1B (0x44) and one -BD1B (0x45) | 2 | $20–40 | Top and bottom of the rack, in small radiation shields |
| ESP32 nodes, IP65 enclosures, wiring | 2–4 | $100–200 | `rack-a-levels` and `rack-a-water` nodes |
| ADS1115 boards (0x48, 0x49, 0x4A) | 3 | $10–15 | 12 moisture channels |
| Cameras, one per level | 6 | $50–150 | Fixed framing, same capture times |

## Site (each)

| Item | Qty | Unit (est.) |
|---|---|---|
| Climate node: ESP32, SHT45 in an aspirated shield, SCD41 CO2, voltage-output PAR sensor + ADS1115 | 1 | $450–800 |
| Portable PAR sensor for mapping all six levels | 1 per program | $300–450 |
| WiFi access point inside the container (a steel shell blocks WiFi) | 1 | $100–200 |
| Gateway: fanless mini PC, or Raspberry Pi 5 8 GB + NVMe SSD (not an SD card) | 1 | $250–400 |
| UPS for gateway, access point and modem | 1 | $100–200 |

## Commissioning checklist

- [ ] Tare and span each reference tray (`tare_raw`, `span_raw`, `span_kg` in `rack-a-levels.yaml`)
- [ ] Read each DS18B20 address from the node log into `temp_addr`
- [ ] Bucket-test each flow meter and set `l_per_pulse`
- [ ] Confirm each valve's feedback follows the real valve, not the timer's command
- [ ] Wet-test each leak sensor
- [ ] Set the CT calibration against a clamp meter
- [ ] Confirm WiFi RSSI is better than −75 dBm at every node
- [ ] Check `/api/unmapped` is empty
- [ ] Register the medium batch, then start a crop cycle on each level

## Not used for AGRIA

There are no reservoir pH, EC or dissolved-oxygen probes and no dosing pumps. AGRIA's nutrition is biological. Soil pH, nutrients and microbial health are measured by lab sampling (see the roadmap).
