"""Alert evaluation.

Threshold alerts are debounced (the value must stay out of band for
``delay_s``) and cleared with hysteresis (it must come back inside the band
by ``hysteresis``), so a value hovering on a limit doesn't page anyone
every 30 seconds.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum

from .config import Thresholds
from .store import Store

log = logging.getLogger(__name__)


class Severity(IntEnum):
    OK = 0
    WARN = 1
    ALARM = 2

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, s: str) -> "Severity":
        return cls[s.upper()]


def classify(value: float, t: Thresholds, shrink: float = 0.0) -> tuple[Severity, str | None]:
    """Severity of ``value`` against ``t``. ``shrink`` narrows the band (used
    for hysteresis when deciding whether an alert can clear). Returns the
    severity and which limit was crossed."""
    if t.alarm_low is not None and value < t.alarm_low + shrink:
        return Severity.ALARM, "alarm_low"
    if t.alarm_high is not None and value > t.alarm_high - shrink:
        return Severity.ALARM, "alarm_high"
    if t.warn_low is not None and value < t.warn_low + shrink:
        return Severity.WARN, "warn_low"
    if t.warn_high is not None and value > t.warn_high - shrink:
        return Severity.WARN, "warn_high"
    return Severity.OK, None


@dataclass
class ThresholdState:
    level: Severity = Severity.OK
    limit: str | None = None
    # When the value first (continuously) reached each severity.
    since: dict[Severity, float] = field(default_factory=dict)

    def step(self, value: float, ts: float, t: Thresholds) -> bool:
        """Advance with a new reading. Returns True if ``level`` changed."""
        raw, limit = classify(value, t)
        for sev in (Severity.WARN, Severity.ALARM):
            if raw >= sev:
                self.since.setdefault(sev, ts)
            else:
                self.since.pop(sev, None)

        target = Severity.OK
        for sev in (Severity.WARN, Severity.ALARM):
            if sev in self.since and ts - self.since[sev] >= t.delay_s:
                target = sev
        if target > self.level:
            self.level, self.limit = target, limit
            return True

        if self.level > Severity.OK:
            cleared, climit = classify(value, t, shrink=t.hysteresis)
            if cleared < self.level:
                self.level, self.limit = cleared, climit
                return True
        return False


@dataclass
class ActiveAlert:
    id: int
    severity: Severity


class AlertManager:
    """Tracks one active alert per (key, kind) and persists to the store."""

    def __init__(self, store: Store, notifier=None):
        self.store = store
        self.notifier = notifier
        self._lock = threading.RLock()
        self.active: dict[tuple[str, str], ActiveAlert] = {}
        for a in store.alerts(active_only=True, limit=10000):
            self.active[(a["key"], a["kind"])] = ActiveAlert(a["id"], Severity.parse(a["severity"]))

    def is_active(self, key: str, kind: str) -> Severity:
        a = self.active.get((key, kind))
        return a.severity if a else Severity.OK

    def raise_(self, key: str, site: str, kind: str, severity: Severity, message: str,
               value: float | None, ts: float) -> None:
        with self._lock:
            cur = self.active.get((key, kind))
            if cur and cur.severity == severity:
                return
            if cur:
                self.store.clear_alert(cur.id, ts)
            aid = self.store.add_alert(key, site, kind, severity.label, message, value, ts)
            self.active[(key, kind)] = ActiveAlert(aid, severity)
        log.warning("ALERT %s %s: %s", severity.label.upper(), key, message)
        if self.notifier:
            self.notifier.send(severity, message, site=site, key=key, kind=kind, resolved=False)

    def clear(self, key: str, site: str, kind: str, ts: float, message: str | None = None) -> None:
        with self._lock:
            cur = self.active.pop((key, kind), None)
            if not cur:
                return
            self.store.clear_alert(cur.id, ts)
        log.info("CLEARED %s %s", key, kind)
        if self.notifier and message:
            self.notifier.send(cur.severity, message, site=site, key=key, kind=kind, resolved=True)
