"""Outbound alert notifications (ntfy push and/or a generic JSON webhook).

Sends run on a background thread so a slow or dead endpoint never blocks
sensor ingest.
"""

from __future__ import annotations

import logging
import queue
import threading

import httpx

from .alerts import Severity
from .config import NotifyCfg

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, cfg: NotifyCfg):
        self.cfg = cfg
        self.min_severity = Severity.parse(cfg.min_severity)
        self._q: queue.Queue = queue.Queue(maxsize=1000)
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.ntfy_url or self.cfg.webhook_url)

    def start(self):
        if self.enabled and not self._thread:
            self._thread = threading.Thread(target=self._run, name="notifier", daemon=True)
            self._thread.start()

    def stop(self):
        if self._thread:
            self._q.put(None)
            self._thread.join(timeout=5)
            self._thread = None

    def send(self, severity: Severity, message: str, *, site: str, key: str, kind: str, resolved: bool):
        if not self.enabled or severity < self.min_severity:
            return
        try:
            self._q.put_nowait(dict(severity=severity, message=message, site=site, key=key, kind=kind, resolved=resolved))
        except queue.Full:
            log.error("notification queue full; dropping: %s", message)

    def _run(self):
        with httpx.Client(timeout=10) as client:
            while (item := self._q.get()) is not None:
                for fn in (self._ntfy, self._webhook):
                    try:
                        fn(client, item)
                    except Exception as e:  # noqa: BLE001 - never let a bad endpoint kill the thread
                        log.error("notification via %s failed: %s", fn.__name__, e)

    def _ntfy(self, client: httpx.Client, item: dict):
        if not self.cfg.ntfy_url:
            return
        sev: Severity = item["severity"]
        if item["resolved"]:
            title, priority, tags = f"Resolved: {item['site']}", "default", "white_check_mark"
        else:
            title = f"{sev.label.upper()}: {item['site']}"
            priority, tags = ("urgent", "rotating_light") if sev == Severity.ALARM else ("high", "warning")
        client.post(self.cfg.ntfy_url, content=item["message"].encode(),
                    headers={"Title": title, "Priority": priority, "Tags": tags}).raise_for_status()

    def _webhook(self, client: httpx.Client, item: dict):
        if not self.cfg.webhook_url:
            return
        body = {**item, "severity": item["severity"].label, "text": item["message"]}
        client.post(self.cfg.webhook_url, json=body).raise_for_status()
