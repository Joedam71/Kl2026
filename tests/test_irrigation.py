from agria.alerts import AlertManager
from agria.hub import Hub

from conftest import SITE, T0, active, send, small_cfg

ZONE = f"{SITE}/irrigation/rack-a-l3"


def water(hub, t, seconds=120, lpm=3.0, start_total=0.0, level=3):
    send(hub, "rack-a-water", f"l{level}_volume", start_total, t)
    send(hub, "rack-a-water", f"l{level}_valve", "ON", t)
    for s in range(0, seconds + 1, 30):
        send(hub, "rack-a-water", f"l{level}_flow", lpm, t + s)
        send(hub, "rack-a-water", f"l{level}_volume", start_total + lpm * s / 60, t + s)
    send(hub, "rack-a-water", f"l{level}_valve", "OFF", t + seconds)
    send(hub, "rack-a-water", f"l{level}_flow", 0, t + seconds + 1)


def test_event_volume_from_meter(hub, store):
    water(hub, T0, seconds=120, lpm=3.0, start_total=100.0)
    ev = store.irrigation_events(site=SITE, zone="rack-a-l3")
    assert len(ev) == 1 and ev[0]["source"] == "meter"
    assert abs(ev[0]["liters"] - 6.0) < 1e-6
    assert ev[0]["end_ts"] - ev[0]["start_ts"] == 120


def test_event_volume_from_flow_integral_without_meter(store, notifier):
    cfg = small_cfg(volume=False)
    hub = Hub(cfg, store, AlertManager(store, notifier), now=T0)
    send(hub, "w", "l1_valve", "ON", T0, site="s")
    for s in range(0, 121, 30):
        send(hub, "w", "l1_flow", 2.0, T0 + s, site="s")
    send(hub, "w", "l1_valve", "OFF", T0 + 120, site="s")
    ev = store.irrigation_events(site="s")
    assert ev[0]["source"] == "flow" and abs(ev[0]["liters"] - 4.0) < 1e-6


def test_valve_open_too_long_and_no_flow(hub, store):
    send(hub, "rack-a-water", "l3_valve", "ON", T0)
    send(hub, "rack-a-water", "l3_flow", 0.0, T0 + 10)
    hub.check(T0 + 60)
    assert active(store)[(ZONE, "no_flow")]["severity"] == "warn"
    send(hub, "rack-a-water", "l3_flow", 3.0, T0 + 70)
    assert (ZONE, "no_flow") not in active(store)
    hub.check(T0 + 1000)
    assert active(store)[(ZONE, "valve_open_too_long")]["severity"] == "alarm"
    send(hub, "rack-a-water", "l3_valve", "OFF", T0 + 1010)
    assert (ZONE, "valve_open_too_long") not in active(store)


def test_flow_with_valve_shut_alarms(hub, store):
    send(hub, "rack-a-water", "l3_valve", "OFF", T0)
    send(hub, "rack-a-water", "l3_flow", 0.6, T0 + 10)
    hub.check(T0 + 40)
    assert (ZONE, "flow_without_valve") not in active(store)  # not yet sustained
    send(hub, "rack-a-water", "l3_flow", 0.6, T0 + 80)
    hub.check(T0 + 80)
    assert active(store)[(ZONE, "flow_without_valve")]["severity"] == "alarm"
    send(hub, "rack-a-water", "l3_flow", 0.0, T0 + 90)
    assert (ZONE, "flow_without_valve") not in active(store)


def test_daily_volume_cap(store, notifier):
    cfg = small_cfg(cap=5.0)
    hub = Hub(cfg, store, AlertManager(store, notifier), now=T0)
    for start in (T0, T0 + 600):
        send(hub, "w", "l1_volume", 0 if start == T0 else 3, start, site="s")
        send(hub, "w", "l1_valve", "ON", start, site="s")
        send(hub, "w", "l1_volume", 3 if start == T0 else 6, start + 60, site="s")
        send(hub, "w", "l1_valve", "OFF", start + 60, site="s")
    assert active(store)[("s/irrigation/r-l1", "daily_volume")]["severity"] == "warn"


def test_restart_mid_watering_still_records_event(cfg, store, notifier, hub):
    send(hub, "rack-a-water", "l3_volume", 50.0, T0)
    send(hub, "rack-a-water", "l3_valve", "ON", T0)
    hub2 = Hub(cfg, store, AlertManager(store, notifier), now=T0 + 30)
    send(hub2, "rack-a-water", "l3_volume", 55.0, T0 + 100)
    send(hub2, "rack-a-water", "l3_valve", "OFF", T0 + 100)
    ev = store.irrigation_events(site=SITE, zone="rack-a-l3")
    assert ev[0]["start_ts"] == T0 and abs(ev[0]["liters"] - 5.0) < 1e-6


def test_liters_today_in_rack_view(hub):
    water(hub, T0, seconds=60, lpm=4.0, start_total=0.0)
    lvl3 = next(l for l in hub.snapshot(now=T0 + 120)[0]["racks"][0]["levels"] if l["level"] == 3)
    assert lvl3["irrigation"]["liters_today"] == 4.0
    assert lvl3["irrigation"]["last_event"]["liters"] == 4.0
