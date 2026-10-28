"""Sensor simulator: publishes realistic data for every sensor in sites.yaml
over MQTT, using the same topics ESPHome nodes use. Lets the gateway,
dashboard and alerting be built and demonstrated before hardware arrives.

    agria-sim --host localhost --interval 5
    agria-sim --speed 60                        # one simulated hour per real minute
    agria-sim --fault container-1/c1-nutrient/ph=drift
    agria-sim --fault greenhouse-1/gh1-climate=offline

Faults: drift (value runs away), stuck (freezes), spike (occasional
implausible readings), offline (node goes silent; on a node key).
"""

from __future__ import annotations

import argparse
import math
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt

from .config import load
from .hub import TOPIC_ROOT


class SiteModel:
    """Plausible diurnal behavior for one site. ``h`` is local hour of day."""

    def __init__(self, site_type: str, rng: random.Random):
        self.container = site_type == "container"
        self.rng = rng
        self.ph = 5.8
        self.ec = 1.8
        self.level = 90.0

    def lights_on(self, h: float) -> bool:
        return 6 <= h < 22  # container photoperiod 16/8

    def values(self, h: float, dt_h: float) -> dict[str, float]:
        n = self.rng.gauss
        if self.container:
            on = self.lights_on(h)
            air = (23.0 if on else 19.5) + n(0, 0.2)
            ppfd = (320.0 + n(0, 5)) if on else 0.0
            co2 = (900.0 if on else 1000.0) + n(0, 25)
        else:
            air = 21.0 + 5.0 * math.sin(2 * math.pi * (h - 9) / 24) + n(0, 0.3)
            ppfd = max(0.0, 950 * math.sin(math.pi * (h - 6) / 14)) if 6 <= h <= 20 else 0.0
            ppfd = max(0.0, ppfd * (1 + n(0, 0.08)))
            co2 = 430 - 40 * (ppfd / 950) + n(0, 10)
        rh = min(95.0, max(30.0, 70.0 - 2.0 * (air - 21.0) + n(0, 1.0)))
        water = 20.5 + 1.2 * math.sin(2 * math.pi * (h - 11) / 24) + n(0, 0.1)

        # Nutrient solution: pH creeps up, EC falls as plants feed; a manual
        # correction resets them. Reservoir drains and gets topped up.
        self.ph += 0.03 * dt_h
        if self.ph > 6.3:
            self.ph = 5.8
        self.ec -= 0.01 * dt_h
        if self.ec < 1.4:
            self.ec = 1.8
        self.level -= 1.2 * dt_h
        if self.level < 35:
            self.level = 92.0
        do = 8.2 - 0.18 * (water - 20) + n(0, 0.05)
        return {
            "air_temperature": air, "relative_humidity": rh, "co2": co2, "ppfd": ppfd,
            "water_temperature": water, "ph": self.ph + n(0, 0.01), "ec": self.ec + n(0, 0.01),
            "dissolved_oxygen": do, "tank_level": self.level + n(0, 0.3),
            "level_switch": 1.0 if self.level > 20 else 0.0,
            "wifi_rssi": (-72.0 if self.container else -61.0) + n(0, 2),
        }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config/sites.yaml")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--interval", type=float, default=10.0, help="real seconds between publishes")
    p.add_argument("--speed", type=float, default=1.0, help="simulated seconds per real second")
    p.add_argument("--fault", action="append", default=[], metavar="KEY=MODE")
    p.add_argument("--seed", type=int)
    args = p.parse_args(argv)

    cfg = load(args.config)
    rng = random.Random(args.seed)
    faults = dict(f.split("=", 1) for f in args.fault)
    models = {s.id: SiteModel(s.type, rng) for s in cfg.sites}
    stuck: dict[str, float] = {}
    drift: dict[str, float] = {}

    clients = {}
    for site in cfg.sites:
        for node in site.nodes:
            prefix = f"{TOPIC_ROOT}/{site.id}/{node.id}"
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{site.id}-{node.id}")
            if args.username:
                c.username_pw_set(args.username, args.password)
            c.will_set(f"{prefix}/status", "offline", retain=True)
            c.connect(args.host, args.port, keepalive=30)
            c.loop_start()
            clients[(site.id, node.id)] = (c, prefix)

    for (site_id, node_id), (c, prefix) in clients.items():
        if faults.get(f"{site_id}/{node_id}") != "offline":
            c.publish(f"{prefix}/status", "online", retain=True)
        else:
            c.publish(f"{prefix}/status", "offline", retain=True)

    sim_t = time.time()
    print(f"simulating {len(cfg.sensors)} sensors across {len(cfg.sites)} sites; Ctrl-C to stop")
    try:
        while True:
            dt = args.interval * args.speed
            sim_t += dt
            for site in cfg.sites:
                lt = datetime.fromtimestamp(sim_t, ZoneInfo(site.timezone))
                vals = models[site.id].values(lt.hour + lt.minute / 60, dt / 3600)
                for node in site.nodes:
                    if faults.get(f"{site.id}/{node.id}") == "offline":
                        continue
                    c, prefix = clients[(site.id, node.id)]
                    for s in node.sensors:
                        key = f"{site.id}/{node.id}/{s.id}"
                        v = vals.get(s.kind)
                        if v is None:
                            continue
                        mode = faults.get(key)
                        if mode == "drift":
                            drift[key] = drift.get(key, 0.0) + 0.5 * dt / 3600 * max(1.0, abs(v) * 0.1)
                            v += drift[key]
                        elif mode == "stuck":
                            v = stuck.setdefault(key, v)
                        elif mode == "spike" and rng.random() < 0.15:
                            v = -127.0
                        if s.kind == "level_switch":
                            c.publish(f"{prefix}/binary_sensor/{s.id}/state", "ON" if v >= 0.5 else "OFF")
                        else:
                            c.publish(f"{prefix}/sensor/{s.id}/state", f"{v:.3f}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        for c, prefix in clients.values():
            c.publish(f"{prefix}/status", "offline", retain=True).wait_for_publish(2)
            c.loop_stop()
            c.disconnect()


if __name__ == "__main__":
    main()
