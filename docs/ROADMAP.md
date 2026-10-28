# Roadmap

Each phase has an exit gate. A phase isn't funded until the previous gate passes. Phases 0 and 1 run in parallel.

| Phase | Scope | Exit gate |
|---|---|---|
| **0. Medium characterization** | Lab tests on 3–5 production batches: water retention curve, field capacity, dry-down rate, bulk density, porosity, drainage; quantitative NPK, micronutrients and pH (following up the 7.5–8.0 pH and low-potassium flags); microbial profile (PLFA, sequencing). Output: the Growing Medium Characterization Specification. | Specification approved by William and the plant-science team, including moisture limits per crop |
| **1. Pilot rack baseline** (this repo) | One six-level rack fully instrumented and run on today's timer for two crop cycles; moisture sensors calibrated against tray weight | Sensors calibrated to the medium; one sensor type selected; 98% data completeness; water use per level measured |
| **2. Irrigation control trial** | Rack-level controller with hardwired limits; timer arm vs sensor-guided arm, swapped between cycles; interruption trials | Sensor-guided matches or beats timer yield with less water per kg and zero overwatering or flood events |
| **3. Scale-out and site climate** | Proven rack package on the remaining racks; site climate monitoring and control; TimescaleDB | All racks within limits; climate in band 95% of the time; outage drills pass |
| **4. AI optimization and vision** | Crop recipes; AI proposes irrigation and climate changes for approval; vision for germination, canopy and stress | AI proposals beat the approved rules over two cycles; vision matches a grower's manual assessment |
| **5. Robotics pilot** | One rail-mounted imaging or handling robot along a rack face, integrated through ROS 2 | A defined job runs unattended for 30 days with a measured benefit |

## Control rules for Phase 2 (design constraints, decided now)

- Irrigation commands are setpoints and modes, never raw valve toggles. The controller can reject a command that falls outside its hard limits and must say why.
- Hardwired, software-independent protection on every level: maximum valve-open time, a daily volume cap, and a master shutoff on any leak sensor.
- Manual override and a visible e-stop at the rack.
- Deterministic rules first. AI only proposes, and a person approves.

## Not planned

- **Automatic nutrient dosing.** AGRIA's nutrition is biological. Soil and microbial sampling stays a lab activity until Phase 0 and trial data justify anything more.
- **Lighting control** until the AGL4MS driver interface and spectral data are verified.
