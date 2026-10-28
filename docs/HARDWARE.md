# Phase 1 hardware

Every part here is commodity hardware and was chosen to keep the first deployment cheap and quick to replace. Prices are rough 2026 estimates in USD. Verify current pricing before ordering.

## Per site (greenhouse or container)

### Climate node (×1)

| Item | Purpose | Est. |
|---|---|---|
| ESP32 dev board (WROOM-32) in an IP65 enclosure | Node controller | $25 |
| Sensirion SHT45 breakout | Air temperature and RH | $20 |
| Aspirated radiation shield (fan-ventilated) | Without one, greenhouse sun inflates readings by several °C | $60–150 |
| Sensirion SCD41 breakout | CO2 (photoacoustic) | $55 |
| Voltage-output quantum (PAR) sensor, e.g. Apogee SQ series | PPFD and DLI. Don't substitute a lux sensor: lux doesn't convert reliably to PPFD under LED light. | $250–400 |
| ADS1115 ADC breakout | Reads the PAR sensor's analog output | $10 |
| 5 V supply, cabling, glands | | $30 |

### Nutrient node (×1 per reservoir)

| Item | Purpose | Est. |
|---|---|---|
| ESP32 dev board in an IP65 enclosure | Node controller | $25 |
| Atlas Scientific EZO-pH kit with lab-grade probe | pH | $200–250 |
| Atlas Scientific EZO-EC kit with K1.0 probe | EC | $250–300 |
| Atlas Scientific EZO-DO kit | Dissolved oxygen (optional at first, but recommended for DWC and NFT) | $300–350 |
| **Electrically isolated** EZO carrier board | Without isolation, the pH and EC probes in the same tank interfere with each other | $50–80 |
| DS18B20 waterproof probe + 4.7 kΩ resistor | Water temperature, also used for temperature compensation | $10 |
| JSN-SR04T waterproof ultrasonic sensor + 5 V→3.3 V level shifter | Reservoir level | $15 |
| Stainless float switch | Independent low-level alarm. It doesn't depend on the ultrasonic reading. | $15 |
| pH 4/7/10 and EC calibration solutions, storage solution | Probes drift, so calibration is required | $60 |

### Camera (×1–2)

An IP camera with an HTTP snapshot URL and PoE or a 5 V supply, mounted on a fixed bracket with fixed framing ($60–150 each). Lock exposure and white balance if the camera allows it; consistent images matter more than resolution for future vision models. In the container, don't let the camera look into the LED fixtures.

**Per-site estimate:** about $1,400–2,100 depending on the DO sensor and the number of cameras.

## Gateway (×1, shared by both sites if they're on the same network)

| Item | Est. |
|---|---|
| Raspberry Pi 5 (8 GB) **with NVMe SSD** (not an SD card), or a fanless N100 mini PC | $120–250 |
| UPS (Pi UPS HAT or a small line-interactive UPS for the gateway, the WiFi access point and the modem) | $50–150 |

When customer deployments start, move to an industrial PC rated for the temperature and humidity range.

## Network

- Use a dedicated 2.4 GHz IoT SSID (ESP32 is 2.4 GHz only), ideally on its own VLAN.
- **The container's steel shell blocks WiFi.** Put an access point inside the container, wired back to the network. Don't rely on signal leaking in through the doors. The gateway tracks each node's RSSI and warns below −75 dBm.
- Give the gateway a fixed IP address. The nodes reach the broker by that address.

## Wiring notes

- ESP32 GPIO is 3.3 V. The JSN-SR04T echo line needs a level shifter.
- Avoid ESP32 strapping pins (0, 2, 5, 12, 15) for sensors. The configs here already do.
- Wire the float switch so that a broken wire reads "low water". Fail toward the alarm, not toward silence.
- Keep probe cables away from pump and fan power cables.

## What Phase 2 will add (not in this repo yet)

An industrial controller with relay or contactor outputs for fans, heaters, vents and pumps, plus hardwired interlocks (high-temperature cutout, dosing-pump runtime timer, float-switch cutoff on irrigation). Candidates: Arduino Opta, Revolution Pi, or a small Siemens or Automation Direct PLC. Choose one when Phase 2 is scoped.
