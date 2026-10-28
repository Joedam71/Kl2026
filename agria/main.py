"""Gateway entry point. Settings come from environment variables (see .env.example)."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .alerts import AlertManager
from .cameras import CameraCapture
from .config import Config, load
from .cycles import Cycles
from .hub import Hub
from .mqtt_client import MqttIngest
from .notify import Notifier
from .store import Store

log = logging.getLogger("agria")


@dataclass
class Settings:
    config_path: str = "config/sites.yaml"
    data_dir: str = "data"
    mqtt_host: str | None = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    http_host: str = "0.0.0.0"
    http_port: int = 8080
    api_token: str | None = None
    check_interval_s: float = 15.0

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            config_path=e("AGRIA_CONFIG", cls.config_path),
            data_dir=e("AGRIA_DATA_DIR", cls.data_dir),
            mqtt_host=e("AGRIA_MQTT_HOST", cls.mqtt_host) or None,
            mqtt_port=int(e("AGRIA_MQTT_PORT", cls.mqtt_port)),
            mqtt_username=e("AGRIA_MQTT_USERNAME") or None,
            mqtt_password=e("AGRIA_MQTT_PASSWORD") or None,
            http_host=e("AGRIA_HTTP_HOST", cls.http_host),
            http_port=int(e("AGRIA_HTTP_PORT", cls.http_port)),
            api_token=e("AGRIA_API_TOKEN") or None,
        )


class Gateway:
    def __init__(self, settings: Settings, cfg: Config | None = None):
        self.settings = settings
        self.cfg = cfg or load(settings.config_path)
        data = Path(settings.data_dir)
        self.image_dir = data / "images"
        self.store = Store(data / "agria.db")
        self.notifier = Notifier(self.cfg.app.notify)
        self.alerts = AlertManager(self.store, self.notifier)
        self.hub = Hub(self.cfg, self.store, self.alerts)
        self.cycles = Cycles(self.cfg, self.store)
        self.mqtt = (MqttIngest(self.hub, settings.mqtt_host, settings.mqtt_port,
                                settings.mqtt_username, settings.mqtt_password)
                     if settings.mqtt_host else None)
        self.cameras = CameraCapture(self.cfg, self.store, self.image_dir)
        self._stop = threading.Event()
        self._maint: threading.Thread | None = None

    def start(self):
        self.notifier.start()
        if self.mqtt:
            self.mqtt.start()
        self.cameras.start()
        self._maint = threading.Thread(target=self._maintenance, name="maintenance", daemon=True)
        self._maint.start()

    def stop(self):
        self._stop.set()
        if self.mqtt:
            self.mqtt.stop()
        self.cameras.stop()
        if self._maint:
            self._maint.join(timeout=5)
        self.notifier.stop()
        self.store.close()

    def _maintenance(self):
        last_retention = 0.0
        while not self._stop.wait(self.settings.check_interval_s):
            try:
                self.hub.check()
                if time.time() - last_retention > 86400:
                    n = self.store.apply_retention(self.cfg.app.retention.raw_days)
                    last_retention = time.time()
                    if n:
                        log.info("retention: rolled up and removed %d raw readings", n)
            except Exception:  # noqa: BLE001
                log.exception("maintenance pass failed")


def run():
    import uvicorn

    from .api import create_app

    logging.basicConfig(level=os.environ.get("AGRIA_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    gw = Gateway(settings)
    log.info("loaded %d sites, %d sensors from %s", len(gw.cfg.sites), len(gw.cfg.sensors), settings.config_path)
    uvicorn.run(create_app(gw), host=settings.http_host, port=settings.http_port, log_level="warning")


if __name__ == "__main__":
    run()
