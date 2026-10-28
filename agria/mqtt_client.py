"""MQTT subscriber feeding the hub. paho's network loop runs on its own
thread and reconnects automatically."""

from __future__ import annotations

import logging

import paho.mqtt.client as mqtt

from .hub import TOPIC_ROOT, Hub

log = logging.getLogger(__name__)


class MqttIngest:
    def __init__(self, hub: Hub, host: str, port: int = 1883, username: str | None = None,
                 password: str | None = None, client_id: str = "agria-gateway"):
        self.hub = hub
        self.host, self.port = host, port
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.enable_logger(log)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        log.info("connecting to MQTT broker %s:%s", self.host, self.port)
        self.client.connect_async(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connect refused: %s", reason_code)
            return
        self.connected = True
        log.info("MQTT connected; subscribing to %s/#", TOPIC_ROOT)
        client.subscribe(f"{TOPIC_ROOT}/#", qos=1)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        log.warning("MQTT disconnected (%s); will retry", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            self.hub.handle_message(msg.topic, msg.payload)
        except Exception:  # noqa: BLE001 - one bad message must not stop ingest
            log.exception("failed to handle %s", msg.topic)
