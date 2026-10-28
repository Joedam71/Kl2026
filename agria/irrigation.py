"""Irrigation delivery monitoring.

Phase 1 doesn't control water; it measures what the existing timer actually
delivers to each rack level and catches delivery faults:

- valve open too long          (alarm)  stuck valve or controller fault
- valve open but no flow       (warn)   pump off, empty supply, clog
- flow while the valve is shut (alarm)  leak or valve not seating
- daily volume over a cap      (warn)   optional, per rack

Every open/close cycle becomes an irrigation event with its volume, which
is what "water per kg harvested" and the Phase 2 trial are computed from.
Volume comes from the meter's cumulative total when the node reports one,
otherwise from integrating the flow rate.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from .alerts import AlertManager, Severity
from .config import Config, Zone
from .derived import local_midnight
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class ZoneState:
    open: bool | None = None
    opened_ts: float | None = None
    open_total: float | None = None   # meter total when the valve opened
    integrated_l: float = 0.0         # flow-rate integral since opening
    flow: tuple[float, float] | None = None   # (ts, L/min)
    total: float | None = None        # latest meter total
    flow_closed_since: float | None = None


class IrrigationMonitor:
    def __init__(self, cfg: Config, store: Store, alerts: AlertManager,
                 latest: dict[str, tuple[float, float]] | None = None):
        self.cfg = cfg
        self.store = store
        self.alerts = alerts
        self._lock = threading.RLock()
        self.state: dict[str, ZoneState] = {z.key: ZoneState() for z in cfg.zones.values()}
        self._by_key: dict[str, tuple[Zone, str]] = {}
        for z in cfg.zones.values():
            self._by_key[z.valve_key] = (z, "valve")
            self._by_key[z.flow_key] = (z, "flow")
            if z.volume_key:
                self._by_key[z.volume_key] = (z, "volume")
        # Restore from the last known readings so a restart mid-watering
        # still closes the event and still times the open valve.
        for z in cfg.zones.values():
            st = self.state[z.key]
            latest = latest or {}
            if z.volume_key in latest:
                st.total = latest[z.volume_key][1]
            if z.flow_key in latest:
                st.flow = latest[z.flow_key]
            if z.valve_key in latest:
                ts, v = latest[z.valve_key]
                st.open = v >= 0.5
                if st.open:
                    st.opened_ts, st.open_total = ts, st.total

    def _name(self, z: Zone) -> str:
        site = self.cfg.site(z.site)
        return f"{site.name if site else z.site} · {z.rack} level {z.level}"

    def on_reading(self, key: str, value: float, ts: float) -> None:
        hit = self._by_key.get(key)
        if not hit:
            return
        z, part = hit
        with self._lock:
            st = self.state[z.key]
            if part == "volume":
                st.total = value
            elif part == "flow":
                self._on_flow(z, st, value, ts)
            else:
                self._on_valve(z, st, value >= 0.5, ts)

    def _on_flow(self, z: Zone, st: ZoneState, lpm: float, ts: float):
        if st.open and st.flow is not None:
            t0, f0 = st.flow
            if ts > t0:
                st.integrated_l += (f0 + lpm) / 2.0 * (ts - t0) / 60.0
        st.flow = (ts, lpm)
        if st.open is False and lpm > z.limits.leak_flow_lpm:
            if st.flow_closed_since is None:
                st.flow_closed_since = ts
        else:
            st.flow_closed_since = None
            self.alerts.clear(z.key, z.site, "flow_without_valve", ts,
                              f"{self._name(z)}: flow with the valve shut has stopped")
        if st.open and lpm >= z.limits.min_flow_lpm:
            self.alerts.clear(z.key, z.site, "no_flow", ts, f"{self._name(z)}: water is flowing again")

    def _on_valve(self, z: Zone, st: ZoneState, is_open: bool, ts: float):
        if is_open and not st.open:
            st.open, st.opened_ts, st.open_total, st.integrated_l = True, ts, st.total, 0.0
            st.flow_closed_since = None
            self.alerts.clear(z.key, z.site, "flow_without_valve", ts)
        elif not is_open and st.open:
            self._close(z, st, ts)
        elif st.open is None:
            st.open = is_open

    def _close(self, z: Zone, st: ZoneState, ts: float):
        liters, source = st.integrated_l, "flow"
        if st.open_total is not None and st.total is not None and st.total >= st.open_total:
            liters, source = st.total - st.open_total, "meter"
        start = st.opened_ts if st.opened_ts is not None else ts
        self.store.add_irrigation_event(z.site, z.id, z.rack, z.level, start, ts, round(liters, 3), source)
        log.info("irrigation %s: %.2f L over %.0f s (%s)", z.key, liters, ts - start, source)
        st.open, st.opened_ts, st.open_total, st.integrated_l = False, None, None, 0.0
        self.alerts.clear(z.key, z.site, "valve_open_too_long", ts, f"{self._name(z)}: valve closed")
        self.alerts.clear(z.key, z.site, "no_flow", ts)
        self._check_daily(z, ts)

    def _check_daily(self, z: Zone, now: float):
        cap = z.limits.daily_volume_cap_l
        if cap is None:
            return
        used = self.liters_today(z, now)
        if used > cap:
            self.alerts.raise_(z.key, z.site, "daily_volume", Severity.WARN,
                               f"{self._name(z)}: {used:.1f} L delivered today, over the {cap:g} L cap", used, now)
        else:
            self.alerts.clear(z.key, z.site, "daily_volume", now)

    def liters_today(self, z: Zone, now: float) -> float:
        tz = self.cfg.site(z.site).timezone
        used = self.store.irrigation_liters(z.site, z.id, local_midnight(now, tz), now)
        st = self.state[z.key]
        if st.open:
            if st.open_total is not None and st.total is not None and st.total >= st.open_total:
                used += st.total - st.open_total
            else:
                used += st.integrated_l
        return used

    def check(self, now: float) -> None:
        with self._lock:
            for z in self.cfg.zones.values():
                st = self.state[z.key]
                name = self._name(z)
                if st.open and st.opened_ts is not None:
                    open_s = now - st.opened_ts
                    if open_s > z.limits.max_open_s:
                        self.alerts.raise_(z.key, z.site, "valve_open_too_long", Severity.ALARM,
                                           f"{name}: valve open {open_s / 60:.0f} min "
                                           f"(limit {z.limits.max_open_s / 60:g} min). Check for a stuck valve.",
                                           None, now)
                    flowing = st.flow is not None and st.flow[0] >= st.opened_ts and st.flow[1] >= z.limits.min_flow_lpm
                    if open_s > z.limits.no_flow_after_s and not flowing:
                        self.alerts.raise_(z.key, z.site, "no_flow", Severity.WARN,
                                           f"{name}: valve open but no water flowing. Check the pump, "
                                           f"supply and lines.", None, now)
                if (st.open is False and st.flow_closed_since is not None
                        and now - st.flow_closed_since > z.limits.flow_without_valve_s):
                    self.alerts.raise_(z.key, z.site, "flow_without_valve", Severity.ALARM,
                                       f"{name}: water flowing ({st.flow[1]:.2f} L/min) with the valve shut. "
                                       f"Possible leak or valve not seating.", st.flow[1], now)
                self._check_daily(z, now)

    def zone_view(self, z: Zone, now: float) -> dict:
        st = self.state[z.key]
        last = self.store.irrigation_events(site=z.site, zone=z.id, limit=1)
        return {
            "zone": z.id, "open": st.open, "opened_ts": st.opened_ts,
            "flow_lpm": st.flow[1] if st.flow else None,
            "liters_today": round(self.liters_today(z, now), 2),
            "last_event": last[0] if last else None,
        }
