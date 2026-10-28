"""The gateway core: turns MQTT messages into stored readings, derived
metrics and alerts.

Topic contract (matches ESPHome's MQTT layout with
``topic_prefix: agria/<site>/<node>``):

    agria/<site>/<node>/sensor/<sensor>/state         numeric payload
    agria/<site>/<node>/binary_sensor/<sensor>/state  ON / OFF
    agria/<site>/<node>/status                        online / offline (LWT)

See docs/MQTT.md.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque

from .alerts import AlertManager, Severity, ThresholdState
from .config import Config, Sensor
from .derived import DliIntegrator, local_midnight, vpd_kpa
from .store import Store

log = logging.getLogger(__name__)

TOPIC_ROOT = "agria"
# Max age gap between temperature and humidity samples used for one VPD value.
VPD_PAIR_WINDOW_S = 120.0
# Implausible readings: raise after FAULT_COUNT within FAULT_WINDOW_S, clear
# once the window passes with none. One-off glitches (a DS18B20 power-on 85.0)
# are dropped silently instead of paging someone twice.
FAULT_WINDOW_S = 600.0
FAULT_COUNT = 3

LIMIT_TEXT = {
    "alarm_low": ("below", "alarm low"),
    "warn_low": ("below", "warning low"),
    "warn_high": ("above", "warning high"),
    "alarm_high": ("above", "alarm high"),
}


def fmt(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:.0f}"


def parse_payload(payload: bytes | str, binary: bool) -> float | None:
    s = payload.decode(errors="replace") if isinstance(payload, bytes) else payload
    s = s.strip()
    if binary:
        return {"ON": 1.0, "OFF": 0.0}.get(s.upper())
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


class Hub:
    def __init__(self, cfg: Config, store: Store, alerts: AlertManager, now: float | None = None):
        self.cfg = cfg
        self.store = store
        self.alerts = alerts
        self._lock = threading.RLock()
        self.started = time.time() if now is None else now

        self.latest: dict[str, tuple[float, float]] = {
            k: v for k, v in store.latest_readings().items() if k in cfg.sensors
        }
        # Staleness is measured from gateway start at the earliest, so a
        # gateway restart doesn't flag every sensor stale before nodes report.
        self.last_seen: dict[str, float] = {k: max(ts, self.started) for k, (ts, _) in self.latest.items()}
        self.thresh: dict[str, ThresholdState] = {}
        for k in cfg.sensors:
            sev = alerts.is_active(k, "threshold")
            if sev:
                self.thresh[k] = ThresholdState(level=sev)
        self.nodes: dict[str, dict] = {}
        self.unmapped: dict[str, dict] = {}
        self._faults: dict[str, deque[float]] = {}
        self.last_cal = store.last_calibrations()

        self._known_nodes = {f"{s.id}/{n.id}" for s in cfg.sites for n in s.nodes}
        self._derived_by_input: dict[str, list[Sensor]] = {}
        self._dli: dict[str, DliIntegrator] = {}
        for sensor in cfg.sensors.values():
            if not sensor.derived:
                continue
            for ref in sensor.derived.inputs.values():
                self._derived_by_input.setdefault(f"{sensor.site}/{ref}", []).append(sensor)
            if sensor.kind == "dli":
                self._restore_dli(sensor)

    # MQTT entry point

    def handle_message(self, topic: str, payload: bytes | str, ts: float | None = None) -> None:
        ts = time.time() if ts is None else ts
        parts = topic.split("/")
        if len(parts) < 4 or parts[0] != TOPIC_ROOT:
            return
        site, node = parts[1], parts[2]
        if len(parts) == 4 and parts[3] == "status":
            if f"{site}/{node}" in self._known_nodes:
                self._node_status(site, node, payload, ts)
            else:
                self._note_unmapped(topic, payload, ts)
            return
        if len(parts) == 6 and parts[3] in ("sensor", "binary_sensor") and parts[5] == "state":
            sensor = self.cfg.sensors.get(f"{site}/{node}/{parts[4]}")
            if sensor is None or sensor.derived:
                self._note_unmapped(topic, payload, ts)
                return
            self.ingest(sensor, parse_payload(payload, parts[3] == "binary_sensor"), ts, raw=payload)

    def _note_unmapped(self, topic: str, payload, ts: float):
        with self._lock:
            u = self.unmapped.setdefault(topic, {"topic": topic, "first_seen": ts, "count": 0})
            u.update(last_seen=ts, count=u["count"] + 1,
                     payload=payload.decode(errors="replace") if isinstance(payload, bytes) else str(payload))
            if u["count"] == 1:
                log.info("unmapped topic %s (add it to sites.yaml if it should be tracked)", topic)

    def _node_status(self, site: str, node: str, payload, ts: float):
        status = (payload.decode(errors="replace") if isinstance(payload, bytes) else str(payload)).strip().lower()
        key = f"{site}/{node}"
        with self._lock:
            self.nodes[key] = {"status": status, "ts": ts}
        name = self._site_name(site)
        if status == "offline":
            self.alerts.raise_(key, site, "node_offline", Severity.WARN,
                               f"{name} · node {node} went offline (lost connection to the gateway)", None, ts)
            # One node-offline alert replaces a stale alert per sensor on that node.
            for s in self.cfg.site_sensors(site):
                if s.node == node:
                    self.alerts.clear(s.key, site, "stale", ts)
        elif status == "online":
            self.alerts.clear(key, site, "node_offline", ts, f"{name} · node {node} is back online")

    # readings

    def ingest(self, sensor: Sensor, value: float | None, ts: float, raw=None) -> None:
        name = f"{self._site_name(sensor.site)} · {sensor.name}"
        lo, hi = sensor.valid or (float("-inf"), float("inf"))
        if value is None or not (lo <= value <= hi):
            shown = raw.decode(errors="replace") if isinstance(raw, bytes) else (raw if raw is not None else value)
            with self._lock:
                recent = self._faults.setdefault(sensor.key, deque())
                recent.append(ts)
                while recent and recent[0] < ts - FAULT_WINDOW_S:
                    recent.popleft()
                n = len(recent)
            log.debug("dropped implausible reading %s=%s", sensor.key, shown)
            if n >= FAULT_COUNT:
                self.alerts.raise_(sensor.key, sensor.site, "sensor_fault", Severity.WARN,
                                   f"{name}: {n} implausible readings in {FAULT_WINDOW_S / 60:.0f} min "
                                   f"(latest: {shown}); check the probe and wiring", value, ts)
            return

        with self._lock:
            self.store.add_reading(sensor.key, ts, value)
            self.latest[sensor.key] = (ts, value)
            self.last_seen[sensor.key] = ts
            state = self.thresh.setdefault(sensor.key, ThresholdState())
            changed = state.step(value, ts, sensor.thresholds)
            recent = self._faults.get(sensor.key)
            faults_recent = bool(recent) and recent[-1] >= ts - FAULT_WINDOW_S

        if not faults_recent:
            self.alerts.clear(sensor.key, sensor.site, "sensor_fault", ts, f"{name} readings are plausible again")
        self.alerts.clear(sensor.key, sensor.site, "stale", ts, f"{name} is reporting again")
        if changed:
            if state.level == Severity.OK:
                self.alerts.clear(sensor.key, sensor.site, "threshold", ts,
                                  f"{name} back in range at {fmt(value)} {sensor.unit}".rstrip())
            else:
                side, label = LIMIT_TEXT[state.limit]
                limit_v = getattr(sensor.thresholds, state.limit)
                msg = f"{name} is {fmt(value)} {sensor.unit}, {side} {label} of {fmt(limit_v)} {sensor.unit}"
                self.alerts.raise_(sensor.key, sensor.site, "threshold", state.level, msg.replace("  ", " "), value, ts)

        for d in self._derived_by_input.get(sensor.key, ()):
            self._update_derived(d, sensor.key, value, ts)

    def _update_derived(self, d: Sensor, input_key: str, value: float, ts: float):
        if d.kind == "dli":
            v = self._dli[d.key].add(ts, value)
            self.ingest(d, round(v, 4), ts)
        elif d.kind == "vpd":
            t_key = f"{d.site}/{d.derived.inputs['temperature']}"
            h_key = f"{d.site}/{d.derived.inputs['humidity']}"
            t, h = self.latest.get(t_key), self.latest.get(h_key)
            if not t or not h or abs(t[0] - h[0]) > VPD_PAIR_WINDOW_S:
                return
            self.ingest(d, round(vpd_kpa(t[1], h[1]), 4), ts)

    def _restore_dli(self, d: Sensor):
        tz = self.cfg.site(d.site).timezone
        integ = DliIntegrator(tz)
        ppfd_key = f"{d.site}/{d.derived.inputs['ppfd']}"
        for ts, v in self.store.readings_since(ppfd_key, local_midnight(self.started, tz)):
            integ.add(ts, v)
        self._dli[d.key] = integ

    # periodic checks

    def check(self, now: float | None = None) -> None:
        """Run time-based checks: stale sensors and calibration due dates."""
        now = time.time() if now is None else now
        for s in self.cfg.sensors.values():
            if s.stale_after_s is not None:
                # A node-offline or sensor-fault alert already explains the silence.
                covered = (self.alerts.is_active(f"{s.site}/{s.node}", "node_offline")
                           or self.alerts.is_active(s.key, "sensor_fault"))
                age = now - self.last_seen.get(s.key, self.started)
                if age > s.stale_after_s and not covered:
                    self.alerts.raise_(s.key, s.site, "stale", Severity.WARN,
                                       f"{self._site_name(s.site)} · {s.name}: no data for {age / 60:.0f} min",
                                       None, now)
            if s.calibration_interval_days:
                self._check_calibration(s, now)

    def _check_calibration(self, s: Sensor, now: float):
        name = f"{self._site_name(s.site)} · {s.name}"
        last = self.last_cal.get(s.key)
        if last is None:
            self.alerts.raise_(s.key, s.site, "calibration", Severity.WARN,
                               f"{name}: no calibration on record. Calibrate the probe and log it.", None, now)
        elif now > last["ts"] + s.calibration_interval_days * 86400:
            days = (now - last["ts"]) / 86400
            self.alerts.raise_(s.key, s.site, "calibration", Severity.WARN,
                               f"{name}: calibration overdue (last done {days:.0f} days ago, "
                               f"interval {s.calibration_interval_days:g} days)", None, now)
        else:
            self.alerts.clear(s.key, s.site, "calibration", now)

    def record_calibration(self, key: str, by: str | None, notes: str | None, ts: float | None = None) -> int:
        ts = time.time() if ts is None else ts
        sensor = self.cfg.sensors[key]
        cid = self.store.add_calibration(key, ts, by, notes)
        with self._lock:
            self.last_cal[key] = {"sensor_key": key, "ts": ts, "by": by, "notes": notes}
        if sensor.calibration_interval_days:
            self._check_calibration(sensor, ts)
        return cid

    # views

    def _site_name(self, site_id: str) -> str:
        s = self.cfg.site(site_id)
        return s.name if s else site_id

    def sensor_view(self, s: Sensor) -> dict:
        latest = self.latest.get(s.key)
        statuses = {k: self.alerts.is_active(s.key, k) for k in ("threshold", "stale", "sensor_fault", "calibration")}
        statuses["node_offline"] = self.alerts.is_active(f"{s.site}/{s.node}", "node_offline")
        worst = max(statuses.values())
        cal = self.last_cal.get(s.key)
        return {
            "key": s.key, "id": s.id, "node": s.node, "name": s.name, "kind": s.kind, "unit": s.unit,
            "zone": s.zone, "derived": s.derived is not None,
            "value": latest[1] if latest else None, "ts": latest[0] if latest else None,
            "status": worst.label,
            "flags": [k for k, v in statuses.items() if v],
            "thresholds": s.thresholds.model_dump(),
            "calibration": None if not s.calibration_interval_days else {
                "interval_days": s.calibration_interval_days,
                "last_ts": cal["ts"] if cal else None,
                "due_ts": cal["ts"] + s.calibration_interval_days * 86400 if cal else None,
            },
        }

    def snapshot(self) -> list[dict]:
        out = []
        for site in self.cfg.sites:
            sensors = [self.sensor_view(s) for s in self.cfg.site_sensors(site.id)]
            nodes = []
            for n in site.nodes:
                st = self.nodes.get(f"{site.id}/{n.id}", {})
                nodes.append({"id": n.id, "description": n.description,
                              "status": st.get("status", "unknown"), "ts": st.get("ts")})
            out.append({"id": site.id, "name": site.name, "type": site.type, "timezone": site.timezone,
                        "nodes": nodes, "sensors": sensors,
                        "cameras": [{"id": c.id, "name": c.name or c.id} for c in site.cameras]})
        return out
