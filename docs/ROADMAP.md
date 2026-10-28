# Roadmap

Each phase has an exit gate. Don't move to the next phase until the current gate is met, because each phase builds the trust the next one depends on.

## Phase 1: Monitor and alert (this repo, now)

Sensors, storage, dashboard, alerts, calibration tracking and camera capture, with **no actuation**.

**Exit gate:**
- 60 days of operation on both sites with at least 98% data completeness per sensor.
- Every alert type has fired for real at least once and was understood by the person who received it.
- A calibration routine is in practice: pH monthly, EC quarterly, with drift between calibrations recorded.
- The thresholds have been tuned for the actual crop.

## Phase 2: Closed-loop climate

Temperature, humidity, airflow and CO2 control.

- The controller runs its own loops locally from setpoints. The gateway sends setpoints and schedules and receives state back over MQTT on `agria/<site>/<node>/cmd/...` (see MQTT.md).
- Hardwired interlocks: high-temperature cutout independent of software, and fans fail on.
- Every command is logged with its source (user, schedule or automation) and acknowledged by the controller.

**Exit gate:** 30 days of control holding VPD and temperature inside the target band at least 95% of the time, with zero unsafe states during forced network or gateway outages.

## Phase 3: Closed-loop irrigation and nutrient dosing

This phase has the highest-consequence actuators. A stuck dosing pump can wipe out a crop.

- Dosing happens in small pulses with a mixing wait and a re-measurement between pulses. A hardware timer caps pump runtime per cycle and per day.
- Dosing is blocked automatically when the probe is stale, faulted, out of calibration, or reading a value that changed implausibly fast.
- An independent float-switch cutoff protects irrigation pumps.
- A manual override and an e-stop are available at the reservoir.

**Exit gate:** 60 days of automated dosing with pH and EC held inside the target band, an audited dosing log, and no manual corrections other than reservoir changes.

## Phase 4: Vision

Train models on the image record Phase 1 has been capturing: canopy cover and growth rate, tipburn and nutrient-deficiency signs, pest detection, and harvest readiness. Inference runs at the edge on a Jetson-class device at the gateway.

## Phase 5: Robotics

Bring in robots through ROS 2 with an MQTT bridge. Candidate tasks include imaging rails or gantries, tray movement, harvesting and scouting. Robots consume the same site model (sites, zones, sensors) and publish into the same alert and command system, with no separate stack. Before this phase, add `zone` and bed or tray identifiers to `sites.yaml` so the physical layout is machine-readable.

## Cloud and fleet (when there are multiple sites)

Add an MQTT bridge or HTTPS push from each gateway to a cloud service for fleet dashboards, grow recipes pushed to sites, cross-site analytics and OTA updates. Make the buy-vs-build decision on the control layer before Phase 2.
