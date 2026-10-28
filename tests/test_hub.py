from agria.alerts import AlertManager
from agria.hub import Hub

from conftest import SITE, T0, active, send

AIR = f"{SITE}/c1-climate/air_temp"


def test_ingest_stores_and_tracks_latest(hub, store):
    send(hub, "c1-climate", "air_temp", 22.5, T0)
    assert hub.latest[AIR] == (T0, 22.5)
    assert store.readings_since(AIR, 0) == [(T0, 22.5)]


def test_threshold_alert_raise_and_clear(hub, store, notifier):
    for i in range(0, 200, 30):
        send(hub, "c1-climate", "air_temp", 36, T0 + i)
    a = active(store)[(AIR, "threshold")]
    assert a["severity"] == "alarm" and "above alarm high of 34" in a["message"]
    send(hub, "c1-climate", "air_temp", 22, T0 + 300)
    assert (AIR, "threshold") not in active(store)
    assert notifier.sent[-1][2]["resolved"] is True


def test_moisture_has_no_invented_thresholds(hub, store):
    for i in range(0, 3600, 60):
        send(hub, "rack-a-levels", "l1_moisture_a", 1.0, T0 + i)
        send(hub, "rack-a-levels", "l1_moisture_b", 65.0, T0 + i)
    assert not [a for a in store.alerts(active_only=True) if a["kind"] == "threshold"]


def test_implausible_values_are_dropped_and_debounced(hub, store):
    key = f"{SITE}/rack-a-levels/l2_medium_temp"
    send(hub, "rack-a-levels", "l2_medium_temp", 85.0, T0)  # DS18B20 power-on glitch: dropped, no alert
    send(hub, "rack-a-levels", "l2_medium_temp", 21.0, T0 + 1)
    assert hub.latest[key] == (T0 + 1, 21.0)
    assert (key, "sensor_fault") not in active(store)
    send(hub, "rack-a-levels", "l2_medium_temp", "nan", T0 + 2)
    send(hub, "rack-a-levels", "l2_medium_temp", -127, T0 + 3)
    assert active(store)[(key, "sensor_fault")]["severity"] == "warn"
    send(hub, "rack-a-levels", "l2_medium_temp", 21.0, T0 + 4)
    assert (key, "sensor_fault") in active(store)
    send(hub, "rack-a-levels", "l2_medium_temp", 21.0, T0 + 700)
    assert (key, "sensor_fault") not in active(store)


def test_leak_sensor_alarms(hub, store):
    send(hub, "rack-a-water", "leak_floor", "ON", T0)
    send(hub, "rack-a-water", "leak_floor", "ON", T0 + 6)
    a = active(store)[(f"{SITE}/rack-a-water/leak_floor", "threshold")]
    assert a["severity"] == "alarm" and a["message"].endswith("Leak under rack: water detected")


def test_vpd_and_dli_derived(hub):
    send(hub, "c1-climate", "air_temp", 25, T0)
    send(hub, "c1-climate", "rh", 50, T0 + 5)
    assert abs(hub.latest[f"{SITE}/derived/vpd"][1] - 1.584) < 0.01
    for i in range(0, 3601, 60):
        send(hub, "c1-climate", "ppfd", 300, T0 + i)
    assert abs(hub.latest[f"{SITE}/derived/dli"][1] - 1.08) < 0.01


def test_stale_detection_skips_binary_and_node_offline(hub, store):
    hub.check(T0 + 400)
    a = active(store)
    assert (AIR, "stale") in a
    assert (f"{SITE}/rack-a-water/l1_valve", "stale") not in a  # binary: publishes on change only
    assert (f"{SITE}/rack-a-water/leak_floor", "stale") not in a
    send(hub, "c1-climate", "air_temp", 22, T0 + 401)
    assert (AIR, "stale") not in active(store)

    hub.handle_message(f"agria/{SITE}/rack-a-levels/status", b"offline", T0 + 402)
    hub.check(T0 + 2000)
    a = active(store)
    assert (f"{SITE}/rack-a-levels", "node_offline") in a
    assert (f"{SITE}/rack-a-levels/l1_weight", "stale") not in a
    rack = hub.snapshot()[0]["racks"][0]
    lvl1 = next(l for l in rack["levels"] if l["level"] == 1)
    assert "node_offline" in lvl1["sensors"]["tray_weight"][0]["flags"]


def test_calibration_tracking(store, notifier):
    from conftest import small_cfg
    cfg = small_cfg(cal_days=30)
    hub = Hub(cfg, store, AlertManager(store, notifier), now=T0)
    key = "s/m/probe"
    hub.check(T0)
    assert active(store)[(key, "calibration")]["severity"] == "warn"
    hub.record_calibration(key, "Joe", "gravimetric, batch B-001", ts=T0 + 10)
    assert (key, "calibration") not in active(store)
    hub.check(T0 + 31 * 86400)
    assert "overdue" in active(store)[(key, "calibration")]["message"]


def test_unmapped_topics_are_reported(hub):
    hub.handle_message(f"agria/{SITE}/c1-climate/sensor/mystery/state", b"1", T0)
    hub.handle_message(f"agria/{SITE}/new-node/status", b"online", T0)
    assert set(hub.unmapped) == {f"agria/{SITE}/c1-climate/sensor/mystery/state", f"agria/{SITE}/new-node/status"}


def test_restart_restores_alert_state_without_duplicates(cfg, store, notifier, hub):
    for i in range(0, 200, 30):
        send(hub, "c1-climate", "air_temp", 36, T0 + i)
    hub2 = Hub(cfg, store, AlertManager(store, notifier), now=T0 + 500)
    send(hub2, "c1-climate", "air_temp", 36, T0 + 510)
    assert len([a for a in store.alerts(active_only=True) if a["kind"] == "threshold"]) == 1
    assert hub2.latest[AIR][1] == 36


def test_rack_view_shape(hub):
    send(hub, "rack-a-levels", "l6_moisture_a", 31.2, T0)
    rack = hub.snapshot()[0]["racks"][0]
    assert [l["level"] for l in rack["levels"]] == [6, 5, 4, 3, 2, 1]
    top = rack["levels"][0]
    assert top["sensors"]["medium_moisture"][0]["value"] == 31.2
    assert top["irrigation"]["zone"] == "rack-a-l6"
    assert {s["id"] for s in rack["sensors"]} >= {"leak_floor", "pump_current", "air_temp_top"}
