"""Crop-cycle records: the unit the pilot trial and, later, the AI are judged on.

One cycle = one crop on one rack level from sowing to harvest, tagged with
the medium batch, inoculation date, variety and irrigation arm (timer or
sensor-guided). Water per kg harvested is computed from that level's
irrigation events over the cycle.
"""

from __future__ import annotations

import time
from statistics import mean

from .config import Config
from .store import Store

IRRIGATION_MODES = ("timer", "sensor", "manual")
STAGES = ("sown", "germination", "establishment", "vegetative", "harvest-ready")
INTERVENTION_KINDS = ("observation", "stage", "manual-watering", "inoculation", "pest", "disease",
                      "thinning", "sample-taken", "equipment", "other")


class CycleError(ValueError):
    pass


class Cycles:
    def __init__(self, cfg: Config, store: Store):
        self.cfg = cfg
        self.store = store

    def _check_level(self, site: str, rack: str, level: int):
        s = self.cfg.site(site)
        r = next((r for r in (s.racks if s else []) if r.id == rack), None)
        if r is None:
            raise CycleError(f"unknown rack {site}/{rack}")
        if not 1 <= level <= r.levels:
            raise CycleError(f"rack {rack} has no level {level}")

    def start(self, *, site: str, rack: str, level: int, variety: str, irrigation_mode: str,
              batch_id: str | None = None, inoculation_ts: float | None = None, notes: str | None = None,
              by: str | None = None, ts: float | None = None) -> int:
        ts = time.time() if ts is None else ts
        self._check_level(site, rack, level)
        if irrigation_mode not in IRRIGATION_MODES:
            raise CycleError(f"irrigation_mode must be one of {IRRIGATION_MODES}")
        if batch_id and not self.store.batch(batch_id):
            raise CycleError(f"unknown medium batch {batch_id!r}; register it first")
        if self.store.active_cycle(site, rack, level):
            raise CycleError(f"{rack} level {level} already has an active cycle")
        cid = self.store.add_cycle(site=site, rack=rack, level=level, batch_id=batch_id,
                                   inoculation_ts=inoculation_ts, variety=variety,
                                   irrigation_mode=irrigation_mode, stage="sown", start_ts=ts,
                                   notes=notes, created_by=by)
        self.store.add_intervention(cid, ts, "stage", "sown", by)
        return cid

    def _get_active(self, cycle_id: int) -> dict:
        c = self.store.cycle(cycle_id)
        if c is None:
            raise CycleError("cycle not found")
        if c["end_ts"] is not None:
            raise CycleError("cycle already harvested")
        return c

    def set_stage(self, cycle_id: int, stage: str, by: str | None = None, ts: float | None = None):
        ts = time.time() if ts is None else ts
        if stage not in STAGES:
            raise CycleError(f"stage must be one of {STAGES}")
        self._get_active(cycle_id)
        self.store.update_cycle(cycle_id, stage=stage)
        self.store.add_intervention(cycle_id, ts, "stage", stage, by)

    def log(self, cycle_id: int, kind: str, notes: str | None, by: str | None = None, ts: float | None = None) -> int:
        if kind not in INTERVENTION_KINDS:
            raise CycleError(f"kind must be one of {INTERVENTION_KINDS}")
        if self.store.cycle(cycle_id) is None:
            raise CycleError("cycle not found")
        return self.store.add_intervention(cycle_id, time.time() if ts is None else ts, kind, notes, by)

    def harvest(self, cycle_id: int, yield_g: float, by: str | None = None, notes: str | None = None,
                ts: float | None = None):
        ts = time.time() if ts is None else ts
        self._get_active(cycle_id)
        if yield_g < 0:
            raise CycleError("yield can't be negative")
        self.store.update_cycle(cycle_id, end_ts=ts, yield_g=yield_g, stage="harvested")
        self.store.add_intervention(cycle_id, ts, "stage", f"harvested {yield_g:g} g" + (f": {notes}" if notes else ""), by)

    def view(self, c: dict, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        end = c["end_ts"] or now
        zone = self.cfg.zone_for(c["site"], c["rack"], c["level"])
        liters = self.store.irrigation_liters(c["site"], zone.id, c["start_ts"], end) if zone else None
        kg = (c["yield_g"] or 0) / 1000
        return {
            **c,
            "days": round((end - c["start_ts"]) / 86400, 1),
            "water_liters": round(liters, 2) if liters is not None else None,
            "liters_per_kg": round(liters / kg, 1) if liters is not None and kg > 0 else None,
            "interventions": self.store.interventions(c["id"]),
        }

    def trial_summary(self, site: str | None = None) -> list[dict]:
        """Completed cycles grouped by variety and irrigation arm: the Phase 2 comparison."""
        groups: dict[tuple[str, str], list[dict]] = {}
        for c in self.store.cycles(site=site, active=False, limit=10000):
            groups.setdefault((c["variety"], c["irrigation_mode"]), []).append(self.view(c))
        out = []
        for (variety, mode), cs in sorted(groups.items()):
            lpk = [c["liters_per_kg"] for c in cs if c["liters_per_kg"] is not None]
            out.append({
                "variety": variety, "irrigation_mode": mode, "cycles": len(cs),
                "mean_yield_g": round(mean(c["yield_g"] for c in cs), 1),
                "mean_liters_per_kg": round(mean(lpk), 1) if lpk else None,
                "mean_interventions": round(mean(
                    sum(1 for i in c["interventions"] if i["kind"] != "stage") for c in cs), 1),
            })
        return out
