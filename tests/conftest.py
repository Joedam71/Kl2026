import pytest

from agria.alerts import AlertManager
from agria.config import load
from agria.hub import Hub
from agria.store import Store

T0 = 1_760_000_000.0  # fixed clock for deterministic tests


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
