# Pilot rack trial protocol (draft for plant-science review)

Goal: determine whether sensor-guided irrigation beats the current fixed timer on one six-level AGRIA rack, measured by water per kg harvested, yield, crop loss and operator interventions.

## Phase 1: baseline (no control changes)

1. **Instrument** all six levels: two moisture sensors (two different types during evaluation), a load-cell reference tray, a medium temperature probe, valve feedback and a flow meter per level, leak sensors and pump current.
2. **Commission:**
   - Tare each reference tray empty.
   - Span it with a known test weight.
   - Bucket-test each flow meter (run water for a timed interval, weigh it, set `l_per_pulse`).
   - Read each DS18B20 address from the node log.
3. **Calibrate the moisture sensors against tray weight.** For each medium batch, take a reference tray from saturated to dry over several days. Record moisture-sensor millivolts against water mass from tray weight, using oven-dry mass from Phase 0. Fit a per-sensor-type curve, and log it in the calibration log with batch ID and method. Pick the sensor type that tracks weight best; the other is dropped.
4. **Run two crop cycles on the existing timer.** Every level is in the `timer` arm. Record the stage changes, interventions and harvest weight per level.
5. **Exit gate:** sensors calibrated to the AGRIA medium, 98% data completeness, and measured water use per level compared with the 6-gallon-per-level planning figure.

## Phase 2: controlled comparison

- **Arms:** three levels on the fixed timer, three on sensor-guided rules. Swap the arms between cycles so level position (light, heat at the top of the rack) doesn't bias the result.
- **Sensor-guided rule (deterministic, not AI):** water when level moisture falls below the approved lower limit. Deliver a fixed pulse, wait for it to redistribute, and re-check. Never exceed the approved upper limit or the hardware volume cap. Plant science approves every limit, from the Phase 0 specification.
- **Same crop and batch in both arms within a cycle.** Record the batch ID and inoculation date on every cycle.
- **Measures:**
  - liters per kg harvested
  - harvest weight per level
  - germination rate
  - crop loss
  - interventions per cycle
  - overwatering events (moisture above the upper limit, or drainage)
- **Interruption trials** (from the xTechSearch 10 white paper): withhold water for 24, 48 and 72 hours on designated levels and record the moisture trajectory and crop response. Run only with plant-science approval and a recovery plan.
- **Exit gate:** sensor-guided levels match or beat timer yield, use less water per kg, and have zero overwatering or flood events across at least two cycles.

## What the gateway provides

| Need | Where |
|---|---|
| Start, stage, log and harvest each cycle | Dashboard rack table, or `/api/cycles` |
| Water delivered per level and per event | Rack table, watering events, `/api/irrigation/events` |
| Liters per kg, arm comparison | Irrigation trial table, `/api/trial/summary` |
| Raw data for analysis | Export 7 days (CSV) per rack, `/api/export.csv` |
| Calibration records | Sensor detail, then Log calibration |
