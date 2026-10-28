import pytest

from agria.alerts import AlertManager
from agria.config import AppCfg, build, load
from agria.hub import Hub
from agria.store import Store

T0 = 1_760_000_000.0  # fixed clock for deterministic tests
SITE = "container-1"


@pytest.fixture
def cfg():
    return load("config/sites.yaml")


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, severity, message, **kw):
        self.sent.append((severity, message, kw))


@pytest.fixture
def notifier():
    return FakeNotifier()


@pytest.fixture
def hub(cfg, store, notifier):
    return Hub(cfg, store, AlertManager(store, notifier), now=T0)


def send(hub, node, sensor, payload, ts, site=SITE):
    binary = isinstance(payload, str) and payload in ("ON", "OFF")
    comp = "binary_sensor" if binary else "sensor"
    hub.handle_message(f"agria/{site}/{node}/{comp}/{sensor}/state", str(payload).encode(), ts)


def active(store):
    return {(a["key"], a["kind"]): a for a in store.alerts(active_only=True)}


def small_cfg(volume=True, cap=None, cal_days=None):
    water = [{"id": "l1_valve", "kind": "valve_state"}, {"id": "l1_flow", "kind": "water_flow"}]
    if volume:
        water.append({"id": "l1_volume", "kind": "water_volume"})
    raw = {"sites": [{
        "id": "s", "name": "S", "racks": [{"id": "r", "levels": 1, "water_node": "w",
                                            "irrigation": {"daily_volume_cap_l": cap}}],
        "nodes": [
            {"id": "w", "per_level": None, "sensors": [dict(x, rack="r", level=1) for x in water]},
            {"id": "m", "sensors": [{"id": "probe", "kind": "medium_moisture", "rack": "r", "level": 1,
                                     "calibration_interval_days": cal_days}]},
        ],
    }]}
    return build(AppCfg.model_validate(raw))
