"""Site configuration: sites, racks, nodes, sensors, thresholds, cameras,
notifications.

Every sensor has a ``kind``. The kind supplies defaults (unit, physically
plausible range, alert thresholds, staleness timeout, calibration interval);
anything set on the sensor in sites.yaml overrides the default.

AGRIA grows in a biologically active, soil-based medium, not a nutrient
solution. Root-zone kinds (medium moisture, tray weight, flow) therefore
ship with NO agronomic thresholds: moisture limits come from the approved
Growing Medium Characterization Specification and are set per site in
sites.yaml once it exists. Defaults here are limited to physical
plausibility and equipment/safety limits.
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
    # Binary kinds publish on change only, so silence is normal for them.
    binary: bool = False


def _t(alarm_low=None, warn_low=None, warn_high=None, alarm_high=None, hysteresis=0.0, delay_s=120.0):
    return Thresholds(
        alarm_low=alarm_low, warn_low=warn_low, warn_high=warn_high,
        alarm_high=alarm_high, hysteresis=hysteresis, delay_s=delay_s,
    )


KINDS: dict[str, KindDefaults] = {
    # Site climate
    "air_temperature": KindDefaults("°C", (-20, 60), _t(10, 16, 28, 34, 0.5)),
    "relative_humidity": KindDefaults("%", (0, 100), _t(35, 50, 80, 90, 2)),
    # 5000 ppm is the OSHA 8-hour exposure limit; this alarm is for people, not plants.
    "co2": KindDefaults("ppm", (0, 10000), _t(None, 350, 1500, 5000, 50)),
    "ppfd": KindDefaults("µmol/m²/s", (0, 2500), _t()),
    "wifi_rssi": KindDefaults("dBm", (-120, 0), _t(-85, -75, None, None, 3, delay_s=600)),

    # Root zone. No agronomic thresholds until the medium specification sets them.
    "medium_moisture": KindDefaults("% VWC", (0, 70), _t()),
    "moisture_raw": KindDefaults("mV", (0, 3300), _t()),
    "tray_weight": KindDefaults("kg", (0, 500), _t()),
    # Wide safety limits only (root and microbial damage), not a crop target.
    "medium_temperature": KindDefaults("°C", (-5, 50), _t(alarm_low=5, alarm_high=35, hysteresis=0.5, delay_s=300)),
    # Research only: logged, never acted on. Soil-solution EC moves with water content.
    "medium_ec": KindDefaults("dS/m", (0, 20), _t()),

    # Water delivery and equipment
    "water_flow": KindDefaults("L/min", (0, 200), _t()),
    "water_volume": KindDefaults("L", (0, 1e9), _t()),  # cumulative meter total
    "valve_state": KindDefaults("", (0, 1), _t(), stale_after_s=None, binary=True),
    "leak": KindDefaults("", (0, 1), _t(alarm_high=0.5, delay_s=5), stale_after_s=None, binary=True),
    "pump_current": KindDefaults("A", (0, 50), _t()),

    # Derived (computed by the gateway, not reported by a node).
    "vpd": KindDefaults("kPa", (0, 6), _t(0.4, 0.6, 1.2, 1.6, 0.05)),
    "dli": KindDefaults("mol/m²/d", (0, 80), _t(), stale_after_s=None),
    "generic": KindDefaults("", None, _t(), stale_after_s=None),
}

DERIVED_NODE = "derived"
LEVEL_TOKEN = "{level}"


class SensorCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    name: str | None = None
    unit: str | None = None
    rack: str | None = None
    level: int | None = None
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


class PerLevelCfg(BaseModel):
    """Sensors repeated on every level of a rack. ``{level}`` in an id or
    name is replaced with the level number."""

    model_config = ConfigDict(extra="forbid")

    rack: str
    levels: list[int]
    sensors: list[SensorCfg]


class NodeCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str | None = None
    sensors: list[SensorCfg] = Field(default_factory=list)
    per_level: PerLevelCfg | None = None

    def all_sensors(self) -> list[SensorCfg]:
        out = list(self.sensors)
        if self.per_level:
            for lvl in self.per_level.levels:
                for s in self.per_level.sensors:
                    out.append(s.model_copy(update={
                        "id": s.id.replace(LEVEL_TOKEN, str(lvl)),
                        "name": s.name.replace(LEVEL_TOKEN, str(lvl)) if s.name else None,
                        "rack": self.per_level.rack, "level": lvl,
                    }))
        return out


class IrrigationLimits(BaseModel):
    """Delivery-safety limits. These protect equipment and the rack from
    flooding; they are not agronomic watering targets."""

    model_config = ConfigDict(extra="forbid")

    max_open_s: float = 900           # alarm if a level's valve stays open longer
    no_flow_after_s: float = 45       # warn if a valve is open this long with no flow
    min_flow_lpm: float = 0.1         # below this counts as "no flow"
    leak_flow_lpm: float = 0.2        # flow above this with the valve closed is suspicious
    flow_without_valve_s: float = 60  # ...for this long -> alarm
    daily_volume_cap_l: float | None = None  # optional per-level daily warning


class RackCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None
    levels: int = 6
    # Node whose sensors are named l<N>_valve, l<N>_flow and optionally l<N>_volume.
    water_node: str | None = None
    irrigation: IrrigationLimits = Field(default_factory=IrrigationLimits)


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
    rack: str | None = None
    level: int | None = None


class SiteCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str = "greenhouse"  # greenhouse | container
    timezone: str = "America/New_York"
    racks: list[RackCfg] = Field(default_factory=list)
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
    raw_days: int = 365


class AppCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sites: list[SiteCfg]
    notify: NotifyCfg = Field(default_factory=NotifyCfg)
    retention: RetentionCfg = Field(default_factory=RetentionCfg)

    @model_validator(mode="after")
    def _validate(self):
        seen = set()
        for site in self.sites:
            if site.id in seen:
                raise ValueError(f"duplicate site id {site.id}")
            seen.add(site.id)
            racks = {r.id: r for r in site.racks}
            if len(racks) != len(site.racks):
                raise ValueError(f"{site.id}: duplicate rack id")
            node_ids = {n.id for n in site.nodes}
            keys = set()
            for node in site.nodes:
                if node.id == DERIVED_NODE:
                    raise ValueError(f"node id {DERIVED_NODE!r} is reserved")
                for s in node.all_sensors():
                    k = f"{node.id}/{s.id}"
                    if k in keys:
                        raise ValueError(f"duplicate sensor {site.id}/{k}")
                    keys.add(k)
                    if s.rack is not None:
                        if s.rack not in racks:
                            raise ValueError(f"{site.id}/{k}: unknown rack {s.rack!r}")
                        if s.level is not None and not 1 <= s.level <= racks[s.rack].levels:
                            raise ValueError(f"{site.id}/{k}: level {s.level} outside rack {s.rack}")
            for r in site.racks:
                if r.water_node is None:
                    continue
                if r.water_node not in node_ids:
                    raise ValueError(f"{site.id}/{r.id}: water_node {r.water_node!r} is not a node")
                for lvl in range(1, r.levels + 1):
                    for part in ("valve", "flow"):
                        if f"{r.water_node}/l{lvl}_{part}" not in keys:
                            raise ValueError(f"{site.id}/{r.id}: missing sensor {r.water_node}/l{lvl}_{part}")
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
    rack: str | None
    level: int | None
    valid: tuple[float, float] | None
    thresholds: Thresholds
    stale_after_s: float | None
    calibration_interval_days: float | None
    binary: bool = False
    derived: DerivedCfg | None = None


@dataclass
class Zone:
    """One irrigation zone = one rack level with its own valve and flow meter."""

    key: str  # site/irrigation/<rack>-l<level>
    id: str
    site: str
    rack: str
    level: int
    valve_key: str
    flow_key: str
    volume_key: str | None
    limits: IrrigationLimits


@dataclass
class Config:
    app: AppCfg
    sensors: dict[str, Sensor] = field(default_factory=dict)
    zones: dict[str, Zone] = field(default_factory=dict)

    @property
    def sites(self) -> list[SiteCfg]:
        return self.app.sites

    def site(self, site_id: str) -> SiteCfg | None:
        return next((s for s in self.app.sites if s.id == site_id), None)

    def site_sensors(self, site_id: str) -> list[Sensor]:
        return [s for s in self.sensors.values() if s.site == site_id]

    def zone_for(self, site: str, rack: str, level: int) -> Zone | None:
        return next((z for z in self.zones.values() if (z.site, z.rack, z.level) == (site, rack, level)), None)


def _resolve(site: str, node: str, s: SensorCfg, derived: DerivedCfg | None = None) -> Sensor:
    d = KINDS[s.kind]
    try:
        # extra="forbid" rejects misspelled keys; pydantic checks types.
        thresholds = Thresholds.model_validate({**d.thresholds.model_dump(), **(s.thresholds or {})})
    except ValueError as e:
        raise ValueError(f"{site}/{node}/{s.id}: bad thresholds: {e}") from None
    valid = d.valid
    if s.valid_min is not None or s.valid_max is not None:
        lo, hi = valid or (float("-inf"), float("inf"))
        valid = (s.valid_min if s.valid_min is not None else lo, s.valid_max if s.valid_max is not None else hi)
    return Sensor(
        key=f"{site}/{node}/{s.id}", site=site, node=node, id=s.id, kind=s.kind,
        name=s.name or s.id.replace("_", " ").title(), unit=s.unit if s.unit is not None else d.unit,
        rack=s.rack, level=s.level, valid=valid, thresholds=thresholds,
        stale_after_s=s.stale_after_s if s.stale_after_s is not None else d.stale_after_s,
        calibration_interval_days=(s.calibration_interval_days if s.calibration_interval_days is not None
                                   else d.calibration_interval_days),
        binary=d.binary, derived=derived,
    )


def build(app: AppCfg) -> Config:
    cfg = Config(app=app)
    for site in app.sites:
        for node in site.nodes:
            for s in node.all_sensors():
                r = _resolve(site.id, node.id, s)
                cfg.sensors[r.key] = r
        for d in site.derived:
            r = _resolve(site.id, DERIVED_NODE, SensorCfg(id=d.id, kind=d.kind, name=d.name,
                                                          thresholds=d.thresholds), derived=d)
            # Derived values go stale only if their inputs do; the inputs carry that alert.
            r.stale_after_s = None
            cfg.sensors[r.key] = r
        for rack in site.racks:
            if not rack.water_node:
                continue
            for lvl in range(1, rack.levels + 1):
                zid = f"{rack.id}-l{lvl}"
                base = f"{site.id}/{rack.water_node}/l{lvl}"
                vol = f"{base}_volume"
                cfg.zones[f"{site.id}/irrigation/{zid}"] = Zone(
                    key=f"{site.id}/irrigation/{zid}", id=zid, site=site.id, rack=rack.id, level=lvl,
                    valve_key=f"{base}_valve", flow_key=f"{base}_flow",
                    volume_key=vol if vol in cfg.sensors else None, limits=rack.irrigation,
                )
    return cfg


def load(path: str | os.PathLike) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return build(AppCfg.model_validate(raw))
