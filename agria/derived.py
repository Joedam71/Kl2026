"""Derived agronomic metrics."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo


def saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """Tetens equation."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def vpd_kpa(temp_c: float, rh_pct: float) -> float:
    """Air vapor pressure deficit. Uses air temperature as a stand-in for leaf
    temperature; add an IR leaf-temperature sensor later for leaf VPD."""
    rh = min(max(rh_pct, 0.0), 100.0)
    return saturation_vapor_pressure_kpa(temp_c) * (1.0 - rh / 100.0)


def local_midnight(ts: float, tz: str) -> float:
    dt = datetime.fromtimestamp(ts, ZoneInfo(tz))
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


class DliIntegrator:
    """Integrates PPFD (µmol/m²/s) into daily light integral (mol/m²/d),
    resetting at local midnight. Gaps longer than ``max_gap_s`` are not
    bridged, so an outage under-reports rather than inventing light."""

    def __init__(self, tz: str, max_gap_s: float = 600.0):
        self.tz = tz
        self.max_gap_s = max_gap_s
        self.day_start: float | None = None
        self.total_mol = 0.0
        self._last: tuple[float, float] | None = None

    def add(self, ts: float, ppfd: float) -> float:
        midnight = local_midnight(ts, self.tz)
        if self.day_start != midnight:
            self.day_start = midnight
            self.total_mol = 0.0
            # Don't integrate across midnight; start fresh from this sample.
            if self._last and self._last[0] < midnight:
                self._last = None
        if self._last is not None:
            t0, p0 = self._last
            dt = ts - t0
            if 0 < dt <= self.max_gap_s:
                self.total_mol += (p0 + ppfd) / 2.0 * dt / 1e6  # trapezoid
        self._last = (ts, max(ppfd, 0.0))
        return self.total_mol
