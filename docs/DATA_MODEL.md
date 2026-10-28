# Data model

The crop cycle is the unit the pilot trial, and later the AI, is judged on. Every number that matters (water per kg, yield, interventions) traces back to one cycle on one rack level.

## Records

| Table | One row per | Key fields |
|---|---|---|
| `readings` | sensor reading | sensor key, timestamp, value |
| `irrigation_events` | valve open/close cycle on a level | site, rack, level, start, end, liters, source (meter or flow) |
| `media_batches` | production batch of medium | **batch ID only**, date received, handling notes |
| `crop_cycles` | crop on a rack level, sowing to harvest | site, rack, level, batch ID, inoculation date, variety, irrigation arm, stage, start, end, harvest weight (g) |
| `interventions` | anything a person did or saw | cycle, time, kind (stage, observation, manual watering, inoculation, pest, disease, thinning, sample taken, equipment, other), notes, who |
| `calibrations` | sensor calibration | sensor, time, who, method and result |
| `alerts` | alert raised | key, kind, severity, message, raised/cleared/acknowledged |

Derived per cycle: days, liters delivered to that level, **liters per kg harvested**. The trial summary groups completed cycles by variety and irrigation arm.

## Trade-secret boundary

The September 2026 IP register classifies the medium formulation and inoculation know-how as trade secrets.

- This system has **no fields** for formulation, ingredient ratios, inoculant identity, concentration or recipe steps, and none should be added.
- A batch is an opaque ID such as `B-2026-014`. The mapping from ID to formulation lives only in the restricted system, which plant science controls.
- The dashboard warns against entering formulation details into batch notes.
- Contractors and engineers can build, operate and analyze everything here without access to the restricted system.
- Exports (`/api/export.csv`) contain sensor data and batch IDs only.

When Phase 4 needs formulation as a model feature, plant science joins it inside the restricted environment by batch ID. It is not copied out.

## Crop recipes (Phase 4)

A recipe is the approved target conditions for a variety: moisture band by growth stage, watering method and volume limits, climate bands and expected cycle length. Recipes are authored by plant science from Phase 0 and trial results and versioned. The AI proposes recipe changes; it doesn't write them.
