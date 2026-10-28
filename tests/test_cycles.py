import pytest

from agria.cycles import CycleError, Cycles

from conftest import SITE, T0
from test_irrigation import water


@pytest.fixture
def cycles(cfg, store):
    store.add_batch("B-001", T0 - 86400, "received sealed", "Joe", T0)
    return Cycles(cfg, store)


def start(cycles, level=3, mode="timer", **kw):
    return cycles.start(site=SITE, rack="rack-a", level=level, variety="mizuna", irrigation_mode=mode,
                        batch_id="B-001", inoculation_ts=T0 - 3600, by="Joe", ts=T0, **kw)


def test_cycle_lifecycle_and_water_per_kg(cycles, store, hub):
    cid = start(cycles)
    water(hub, T0 + 3600, seconds=120, lpm=3.0)          # 6 L
    water(hub, T0 + 86400, seconds=120, lpm=3.0, start_total=6.0)  # 6 L
    cycles.set_stage(cid, "germination", by="Joe", ts=T0 + 2 * 86400)
    cycles.log(cid, "observation", "even emergence", by="Joe", ts=T0 + 2 * 86400)
    cycles.harvest(cid, 2400, by="Joe", ts=T0 + 35 * 86400)
    v = cycles.view(store.cycle(cid))
    assert v["water_liters"] == 12.0 and v["liters_per_kg"] == 5.0 and v["days"] == 35.0
    assert [i["kind"] for i in v["interventions"]] == ["stage", "stage", "observation", "stage"]


def test_one_active_cycle_per_level_and_validation(cycles):
    start(cycles)
    with pytest.raises(CycleError, match="already"):
        start(cycles)
    with pytest.raises(CycleError, match="no level"):
        start(cycles, level=7)
    with pytest.raises(CycleError, match="irrigation_mode"):
        start(cycles, level=2, mode="sometimes")
    with pytest.raises(CycleError, match="unknown medium batch"):
        cycles.start(site=SITE, rack="rack-a", level=1, variety="x", irrigation_mode="timer", batch_id="NOPE")


def test_trial_summary_compares_arms(cycles, hub):
    a = start(cycles, level=1, mode="timer")
    b = start(cycles, level=2, mode="sensor")
    water(hub, T0 + 100, seconds=120, lpm=3.0, level=1)                 # 6 L
    water(hub, T0 + 100, seconds=60, lpm=3.0, level=2, start_total=0)   # 3 L
    cycles.harvest(a, 2000, ts=T0 + 30 * 86400)
    cycles.harvest(b, 2000, ts=T0 + 30 * 86400)
    s = {r["irrigation_mode"]: r for r in cycles.trial_summary(SITE)}
    assert s["timer"]["mean_liters_per_kg"] == 3.0 and s["sensor"]["mean_liters_per_kg"] == 1.5
