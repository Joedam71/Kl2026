"""Scheduled still capture from cameras that expose an HTTP snapshot URL
(most IP cameras, ESP32-CAM, or a Pi camera behind a small HTTP server).

These images are the time-lapse record now and the training set for
growth, pest and disease models later, so capture consistently: fixed
mount, fixed framing, same times of day.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import Config
from .store import Store

log = logging.getLogger(__name__)


class CameraCapture:
    def __init__(self, cfg: Config, store: Store, image_dir: str | Path):
        self.cfg = cfg
        self.store = store
        self.image_dir = Path(image_dir)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._next: dict[tuple[str, str], float] = {}

    def start(self):
        if any(s.cameras for s in self.cfg.sites) and not self._thread:
            self._thread = threading.Thread(target=self._run, name="cameras", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=15)

    def _run(self):
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            while not self._stop.is_set():
                now = time.time()
                for site in self.cfg.sites:
                    for cam in site.cameras:
                        k = (site.id, cam.id)
                        if now >= self._next.get(k, 0):
                            self._next[k] = now + cam.interval_s
                            self.capture(client, site.id, cam.id, cam.snapshot_url, now)
                self._stop.wait(5)

    def capture(self, client: httpx.Client, site: str, cam: str, url: str, ts: float) -> Path | None:
        try:
            r = client.get(url)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            log.warning("camera %s/%s capture failed: %s", site, cam, e)
            return None
        dt = datetime.fromtimestamp(ts, timezone.utc)
        rel = Path(site) / cam / dt.strftime("%Y/%m/%d") / f"{dt.strftime('%Y%m%dT%H%M%SZ')}.jpg"
        path = self.image_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        self.store.add_image(site, cam, ts, str(rel))
        return path
