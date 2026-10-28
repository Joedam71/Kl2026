from agria.alerts import AlertManager, Severity
from agria.hub import Hub

from conftest import T0

PH = "agria/container-1/c1-nutrient/sensor/ph/state"


def active(store):
    return {(a["key"], a["kind"]): a for a in store.alerts(active_only=True)}


def test_ingest_stores_and_tracks_latest(hub, store):
    hub.handle_message(PH, b"5.9", T0)
    assert hub.latest["container-1/c1-nutrient/ph"] == (T0, 5.9)
    assert store.readings_since("container-1/c1-nutrient/ph", 0) == [(T0, 5.9)]


def test_threshold_alert_raise_and_clear(hub, store, notifier):
    for i in range(0, 200, 30):
        hub.handle_message(PH, b"7.3", T0 + i)
    a = active(store)[("container-1/c1-nutrient/ph", "threshold")]
    assert a["severity"] == "alarm" and "above alarm high of 7 pH" in a["message"]
    hub.handle_message(PH, b"6.0", T0 + 300)
    assert ("container-1/c1-nutrient/ph", "threshold") not in active(store)
    assert notifier.sent[-1][2]["resolved"] is True


def test_implausible_values_are_dropped_and_debounced(hub, store):
    key = "greenhouse-1/gh1-nutrient/water_temp"
    topic = "agria/greenhouse-1/gh1-nutrient/sensor/water_temp/state"
    hub.handle_message(topic, b"85.0", T0)  # one-off DS18B20 glitch: dropped, no alert
    hub.handle_message(topic, b"21.0", T0 + 1)
    assert hub.latest[key] == (T0 + 1, 21.0)
    assert (key, "sensor_fault") not in active(store)
    hub.handle_message(topic, b"nan", T0 + 2)
    hub.handle_message(topic, b"-127", T0 + 3)
    assert active(store)[(key, "sensor_fault")]["severity"] == "warn"
    hub.handle_message(topic, b"21.0", T0 + 4)  # good again, but faults are recent
    assert (key, "sensor_fault") in active(store)
    hub.handle_message(topic, b"21.0", T0 + 700)
    assert (key, "sensor_fault") not in active(store)
    assert hub.latest[key] == (T0 + 700, 21.0)


def test_binary_float_switch(hub, store):
    topic = "agria/greenhouse-1/gh1-nutrient/binary_sensor/tank_low/state"
    hub.handle_message(topic, b"OFF", T0)
    hub.handle_message(topic, b"OFF", T0 + 31)
    assert active(store)[("greenhouse-1/gh1-nutrient/tank_low", "threshold")]["severity"] == "alarm"


def test_vpd_derived_from_temp_and_rh(hub):
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/air_temp/state", b"25", T0)
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/rh/state", b"50", T0 + 5)
    ts, v = hub.latest["greenhouse-1/derived/vpd"]
    assert abs(v - 1.584) < 0.01


def test_vpd_not_computed_from_mismatched_samples(hub):
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/air_temp/state", b"25", T0)
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/rh/state", b"50", T0 + 600)
    assert "greenhouse-1/derived/vpd" not in hub.latest


def test_dli_accumulates(hub):
    for i in range(0, 3601, 60):
        hub.handle_message("agria/container-1/c1-climate/sensor/ppfd/state", b"300", T0 + i)
    assert abs(hub.latest["container-1/derived/dli"][1] - 1.08) < 0.01


def test_stale_detection_and_node_offline_suppression(hub, store):
    hub.check(T0 + 400)
    a = active(store)
    assert ("greenhouse-1/gh1-climate/air_temp", "stale") in a
    # Derived sensors never go stale on their own.
    assert not any(k[0].endswith("/derived/vpd") for k in a)
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/air_temp/state", b"22", T0 + 401)
    assert ("greenhouse-1/gh1-climate/air_temp", "stale") not in active(store)

    assert ("container-1/c1-climate/co2", "stale") in active(store)
    hub.handle_message("agria/container-1/c1-climate/status", b"offline", T0 + 402)
    hub.check(T0 + 2000)
    a = active(store)
    assert ("container-1/c1-climate", "node_offline") in a
    assert ("container-1/c1-climate/co2", "stale") not in a  # suppressed while node is down
    co2 = next(x for x in hub.snapshot()[1]["sensors"] if x["id"] == "co2")
    assert co2["status"] == "warn" and "node_offline" in co2["flags"]
    hub.handle_message("agria/container-1/c1-climate/status", b"online", T0 + 2001)
    assert ("container-1/c1-climate", "node_offline") not in active(store)


def test_calibration_tracking(hub, store):
    key = "container-1/c1-nutrient/ph"
    hub.check(T0)
    assert active(store)[(key, "calibration")]["severity"] == "warn"
    hub.record_calibration(key, "Joe", "pH 4/7 two-point", ts=T0 + 10)
    assert (key, "calibration") not in active(store)
    hub.check(T0 + 31 * 86400)
    assert "overdue" in active(store)[(key, "calibration")]["message"]


def test_unmapped_topics_are_reported(hub):
    hub.handle_message("agria/greenhouse-1/gh1-climate/sensor/mystery/state", b"1", T0)
    hub.handle_message("agria/greenhouse-1/new-node/status", b"online", T0)
    assert set(hub.unmapped) == {"agria/greenhouse-1/gh1-climate/sensor/mystery/state",
                                 "agria/greenhouse-1/new-node/status"}


def test_restart_restores_alert_state_without_duplicates(cfg, store, notifier, hub):
    for i in range(0, 200, 30):
        hub.handle_message(PH, b"7.3", T0 + i)
    hub2 = Hub(cfg, store, AlertManager(store, notifier), now=T0 + 500)
    hub2.handle_message(PH, b"7.3", T0 + 510)
    alarms = [a for a in store.alerts(active_only=True) if a["kind"] == "threshold"]
    assert len(alarms) == 1
    assert hub2.latest["container-1/c1-nutrient/ph"][1] == 7.3
