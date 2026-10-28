"""Site configuration: sites, nodes, sensors, thresholds, cameras, notifications.

Every sensor has a ``kind``. The kind supplies defaults (unit, physically
plausible range, alert thresholds, staleness timeout, calibration interval);
anything set on the sensor in sites.yaml overrides the default.

Default thresholds assume leafy greens / herbs in hydroponics. Tune them per
crop in sites.yaml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alarm_low: float | None = None
    warn_low: float | None = None
    warn_high: float | None = None
    alarm_high: float | None = None
    # Value must come back inside the band by this much before an alert clears.
    hysteresis: float = 0.0
    # Value must stay out of band this long before an alert is raised.
    delay_s: float = 120.0


@dataclass(frozen=True)
class KindDefaults:
    unit: str
    valid: tuple[float, float] | None
    thresholds: Thresholds
    stale_after_s: float | None = 300.0
    calibration_interval_days: float | None = None


def _t(alarm_low=None, warn_low=None, warn_high=None, alarm_high=None, hysteresis=0.0, delay_s=120.0):
    return Thresholds(
        alarm_low=alarm_low, warn_low=warn_low, warn_high=warn_high,
        alarm_high=alarm_high, hysteresis=hysteresis, delay_s=delay_s,
    )


KINDS: dict[str, KindDefaults] = {
    "air_temperature": KindDefaults("°C", (-20, 60), _t(10, 16, 28, 34, 0.5)),
    "relative_humidity": KindDefaults("%", (0, 100), _t(35, 50, 80, 90, 2)),
    # 5000 ppm is the OSHA 8-hour exposure limit; this alarm is for people, not plants.
    "co2": KindDefaults("ppm", (0, 10000), _t(None, 350, 1500, 5000, 50)),
    "ppfd": KindDefaults("µmol/m²/s", (0, 2500), _t()),
    # DS18B20 reports 85.0 on power-up and -127 when disconnected; both fall outside this range.
    "water_temperature": KindDefaults("°C", (0, 45), _t(15, 18, 24, 27, 0.3)),
    "ph": KindDefaults("pH", (1, 13), _t(5.0, 5.5, 6.5, 7.0, 0.05), calibration_interval_days=30),
    "ec": KindDefaults("mS/cm", (0, 10), _t(0.8, 1.2, 2.4, 3.0, 0.05), calibration_interval_days=90),
    "dissolved_oxygen": KindDefaults("mg/L", (0, 20), _t(4, 6, None, None, 0.2), calibration_interval_days=30),
    "tank_level": KindDefaults("%", (-5, 105), _t(15, 30, None, None, 2)),
    # Float switch: 1 = water present, 0 = low. Alarms immediately-ish when it drops.
    "level_switch": KindDefaults("", (0, 1), _t(alarm_low=0.5, delay_s=30)),
    "wifi_rssi": KindDefaults("dBm", (-120, 0), _t(-85, -75, None, None, 3, delay_s=600)),
    # Derived (computed by the gateway, not reported by a node).
    "vpd": KindDefaults("kPa", (0, 6), _t(0.4, 0.6, 1.2, 1.6, 0.05)),
    "dli": KindDefaults("mol/m²/d", (0, 80), _t(), stale_after_s=None),
    "generic": KindDefaults("", None, _t(), stale_after_s=None),
}

DERIVED_NODE = "derived"


class SensorCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    name: str | None = None
    unit: str | None = None
    zone: str | None = None
    valid_min: float | None = None
    valid_max: float | None = None
    thresholds: dict | None = None
    stale_after_s: float | None = None
    calibration_interval_days: float | None = None

    @model_validator(mode="after")
    def _known_kind(self):
        if self.kind not in KINDS:
            raise ValueError(f"sensor {self.id}: unknown kind {self.kind!r} (known: {', '.join(KINDS)})")
        return self


class NodeCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str | None = None
    sensors: list[SensorCfg] = Field(default_factory=list)


class DerivedCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str  # vpd | dli
    name: str | None = None
    # Input sensor references as "node/sensor" within the same site.
    inputs: dict[str, str]
    thresholds: dict | None = None

    @model_validator(mode="after")
    def _check(self):
        need = {"vpd": {"temperature", "humidity"}, "dli": {"ppfd"}}
        if self.kind not in need:
            raise ValueError(f"derived {self.id}: kind must be one of {sorted(need)}")
        missing = need[self.kind] - set(self.inputs)
        if missing:
            raise ValueError(f"derived {self.id}: missing inputs {sorted(missing)}")
        return self


class CameraCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    snapshot_url: str
    interval_s: float = 900


class SiteCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str = "greenhouse"  # greenhouse | container
    timezone: str = "America/New_York"
    nodes: list[NodeCfg] = Field(default_factory=list)
    derived: list[DerivedCfg] = Field(default_factory=list)
    cameras: list[CameraCfg] = Field(default_factory=list)


class NotifyCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ntfy.sh (or self-hosted ntfy) topic URL for phone push, e.g. https://ntfy.sh/agria-xyz
    ntfy_url: str | None = None
    # Generic JSON webhook (Slack/Teams/n8n/etc. adapters can sit behind this).
    webhook_url: str | None = None
    # Lowest severity that gets pushed: warn | alarm
    min_severity: str = "warn"


class RetentionCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Raw readings older than this are rolled up to hourly mean/min/max and deleted.
    raw_days: int = 90


class AppCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: list[SiteCfg]
    notify: NotifyCfg = Field(default_factory=NotifyCfg)
    retention: RetentionCfg = Field(default_factory=RetentionCfg)

    @model_validator(mode="after")
    def _unique(self):
        seen = set()
        for site in self.sites:
            if site.id in seen:
                raise ValueError(f"duplicate site id {site.id}")
            seen.add(site.id)
            keys = set()
            for node in site.nodes:
                if node.id == DERIVED_NODE:
                    raise ValueError(f"node id {DERIVED_NODE!r} is reserved")
                for s in node.sensors:
                    k = f"{node.id}/{s.id}"
                    if k in keys:
                        raise ValueError(f"duplicate sensor {site.id}/{k}")
                    keys.add(k)
            for d in site.derived:
                for ref in d.inputs.values():
                    if ref not in keys:
                        raise ValueError(f"derived {site.id}/{d.id}: input {ref!r} is not a configured sensor")
        return self


@dataclass
class Sensor:
    """A fully resolved sensor (config merged over kind defaults)."""

    key: str  # site/node/sensor
    site: str
    node: str
    id: str
    kind: str
    name: str
    unit: str
    zone: str | None
    valid: tuple[float, float] | None
    thresholds: Thresholds
    stale_after_s: float | None
    calibration_interval_days: float | None
    derived: DerivedCfg | None = None


@dataclass
class Config:
    app: AppCfg
    sensors: dict[str, Sensor] = field(default_factory=dict)

    @property
    def sites(self) -> list[SiteCfg]:
        return self.app.sites

    def site(self, site_id: str) -> SiteCfg | None:
        return next((s for s in self.app.sites if s.id == site_id), None)

    def site_sensors(self, site_id: str) -> list[Sensor]:
        return [s for s in self.sensors.values() if s.site == site_id]


def _resolve(site: str, node: str, sid: str, kind: str, name: str | None, unit: str | None,
             zone: str | None, valid_min, valid_max, overrides: dict | None,
             stale, cal, derived: DerivedCfg | None = None) -> Sensor:
    d = KINDS[kind]
    try:
        # extra="forbid" rejects misspelled keys; pydantic checks types.
        thresholds = Thresholds.model_validate({**d.thresholds.model_dump(), **(overrides or {})})
    except ValueError as e:
        raise ValueError(f"{site}/{node}/{sid}: bad thresholds: {e}") from None
    valid = d.valid
    if valid_min is not None or valid_max is not None:
        lo, hi = valid or (float("-inf"), float("inf"))
        valid = (valid_min if valid_min is not None else lo, valid_max if valid_max is not None else hi)
    return Sensor(
        key=f"{site}/{node}/{sid}", site=site, node=node, id=sid, kind=kind,
        name=name or sid.replace("_", " ").title(), unit=unit if unit is not None else d.unit,
        zone=zone, valid=valid, thresholds=thresholds,
        stale_after_s=stale if stale is not None else d.stale_after_s,
        calibration_interval_days=cal if cal is not None else d.calibration_interval_days,
        derived=derived,
    )


def build(app: AppCfg) -> Config:
    cfg = Config(app=app)
    for site in app.sites:
        for node in site.nodes:
            for s in node.sensors:
                r = _resolve(site.id, node.id, s.id, s.kind, s.name, s.unit, s.zone, s.valid_min,
                             s.valid_max, s.thresholds, s.stale_after_s, s.calibration_interval_days)
                cfg.sensors[r.key] = r
        for d in site.derived:
            r = _resolve(site.id, DERIVED_NODE, d.id, d.kind, d.name, None, None, None, None,
                         d.thresholds, None, None, derived=d)
            # Derived values go stale only if their inputs do; the inputs carry that alert.
            r.stale_after_s = None
            cfg.sensors[r.key] = r
    return cfg


def load(path: str | os.PathLike) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return build(AppCfg.model_validate(raw))
