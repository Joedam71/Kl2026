"""Sensor simulator: publishes plausible data for every sensor in sites.yaml
over MQTT, on the same topics ESPHome nodes use, so the gateway, dashboard,
irrigation monitoring and alerting can be exercised before hardware exists.

The root-zone model is illustrative only. It does NOT represent measured
AGRIA medium behavior: the dry-down rate, field capacity and drainage below
are placeholders until the Phase 0 characterization replaces them.

    agria-sim --host localhost --interval 5
    agria-sim --speed 60                                   # 1 simulated hour per real minute
    agria-sim --fault container-1/rack-a-l3=stuck_valve    # valve never closes
    agria-sim --fault container-1/rack-a-l2=no_water       # valve opens, nothing flows
    agria-sim --fault container-1/rack-a-l5=leak           # flow with the valve shut, floor leak sensor wet
    agria-sim --fault container-1/rack-a-levels/l4_moisture_a=drift
    agria-sim --fault container-1/c1-climate=offline

Sensor faults: drift, stuck, spike. Node fault: offline. Zone faults
(site/<rack>-l<level>): stuck_valve, no_water, leak.
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

# Placeholder physical model (see module docstring).
LEVEL_MEDIUM_L = 151.0      # 32 sq ft x 2 in
REF_TRAY_FRACTION = 1 / 8   # reference tray on load cells = 1/8 of the shelf
TRAY_TARE_KG = 9.0
FIELD_CAPACITY_PCT = 42.0   # excess drains away
FLOW_LPM = 3.0
WATERING_TIMES_H = (6.0, 18.0)


def climate(site_type: str, h: float, rng: random.Random) -> dict[str, float]:
    n = rng.gauss
    if site_type == "container":
        on = 6 <= h < 22
        air = (23.0 if on else 19.5) + n(0, 0.2)
        ppfd = (320.0 + n(0, 5)) if on else 0.0
        co2 = (900.0 if on else 1000.0) + n(0, 25)
    else:
        air = 21.0 + 5.0 * math.sin(2 * math.pi * (h - 9) / 24) + n(0, 0.3)
        ppfd = max(0.0, 950 * math.sin(math.pi * (h - 6) / 14)) if 6 <= h <= 20 else 0.0
        ppfd = max(0.0, ppfd * (1 + n(0, 0.08)))
        co2 = 430 - 40 * (ppfd / 950) + n(0, 10)
    rh = min(95.0, max(30.0, 70.0 - 2.0 * (air - 21.0) + n(0, 1.0)))
    return {"air_temperature": air, "relative_humidity": rh, "co2": co2, "ppfd": ppfd}


class Level:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.vwc = 30.0 + rng.uniform(-3, 3)
        self.total_l = 0.0
        self.valve = False
        self.flow = 0.0

    def step(self, dt_s: float, air: float, vpd: float, lights: bool, open_s: float, valve_open: bool,
             fault: str | None):
        if fault == "stuck_valve" and (valve_open or self.valve):
            valve_open = True
        self.valve = valve_open
        flow = FLOW_LPM if valve_open else 0.0
        if fault == "no_water":
            flow = 0.0
        if fault == "leak" and not valve_open:
            flow = 0.6
        self.flow = max(0.0, flow * (1 + self.rng.gauss(0, 0.03))) if flow else 0.0
        liters = self.flow * dt_s / 60.0
        self.total_l += liters
        self.vwc = min(FIELD_CAPACITY_PCT, self.vwc + liters / LEVEL_MEDIUM_L * 100 * 0.9)
        et = (0.12 + 0.18 * vpd) * (1.3 if lights else 0.5) * dt_s / 3600
        self.vwc = max(8.0, self.vwc - et)
        self.medium_temp = 0.6 * air + 0.4 * 20.0

    def values(self) -> dict[str, float]:
        n = self.rng.gauss
        tray_water = self.vwc / 100 * LEVEL_MEDIUM_L * REF_TRAY_FRACTION
        return {
            "moisture_a": self.vwc + n(0, 0.3),
            "moisture_b": self.vwc * 0.92 + 1.5 + n(0, 0.4),   # a second sensor type reads differently
            "moisture_a_mv": 800 + self.vwc * 35 + n(0, 5),
            "moisture_b_mv": 1000 + self.vwc * 28 + n(0, 5),
            "tray_weight": TRAY_TARE_KG + tray_water + n(0, 0.01),
            "medium_temperature": self.medium_temp + n(0, 0.1),
        }


def in_window(h: float, open_h: float) -> bool:
    return any(t <= h < t + open_h for t in WATERING_TIMES_H)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="config/sites.yaml")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--interval", type=float, default=10.0, help="real seconds between publishes")
    p.add_argument("--speed", type=float, default=1.0, help="simulated seconds per real second")
    p.add_argument("--water-seconds", type=float, default=150.0, help="timer watering length per event")
    p.add_argument("--fault", action="append", default=[], metavar="KEY=MODE")
    p.add_argument("--seed", type=int)
    args = p.parse_args(argv)

    cfg = load(args.config)
    rng = random.Random(args.seed)
    faults = dict(f.split("=", 1) for f in args.fault)
    dt = args.interval * args.speed
    open_s = max(args.water_seconds, 2 * dt)  # a watering must span at least two publishes
    if open_s != args.water_seconds:
        print(f"note: watering lengthened to {open_s:.0f} s so it spans at least two publishes at this speed")
    levels = {(z.site, z.rack, z.level): Level(rng) for z in cfg.zones.values()}
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
            down = faults.get(f"{site.id}/{node.id}") == "offline"
            c.publish(f"{prefix}/status", "offline" if down else "online", retain=True)
            clients[(site.id, node.id)] = (c, prefix)

    sim_t = time.time()
    print(f"simulating {len(cfg.sensors)} sensors and {len(cfg.zones)} irrigation zones; Ctrl-C to stop")
    try:
        while True:
            sim_t += dt
            for site in cfg.sites:
                lt = datetime.fromtimestamp(sim_t, ZoneInfo(site.timezone))
                h = lt.hour + lt.minute / 60 + lt.second / 3600
                clim = climate(site.type, h, rng)
                svp = 0.6108 * math.exp(17.27 * clim["air_temperature"] / (clim["air_temperature"] + 237.3))
                vpd = svp * (1 - clim["relative_humidity"] / 100)
                lights = clim["ppfd"] > 50
                for (s_id, rack, lvl), lv in levels.items():
                    if s_id == site.id:
                        lv.step(dt, clim["air_temperature"], vpd, lights, open_s,
                                in_window(h, open_s / 3600), faults.get(f"{site.id}/{rack}-l{lvl}"))
                for node in site.nodes:
                    if faults.get(f"{site.id}/{node.id}") == "offline":
                        continue
                    c, prefix = clients[(site.id, node.id)]
                    for s in node.all_sensors():
                        key = f"{site.id}/{node.id}/{s.id}"
                        v = sensor_value(s, site.id, clim, levels, faults, rng)
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
                        if s.kind in ("valve_state", "leak"):
                            c.publish(f"{prefix}/binary_sensor/{s.id}/state", "ON" if v >= 0.5 else "OFF", retain=True)
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


def sensor_value(s, site_id, clim, levels, faults, rng) -> float | None:
    if s.level is not None:
        lv = levels.get((site_id, s.rack, s.level))
        if lv is None:
            return None
        if s.kind == "valve_state":
            return 1.0 if lv.valve else 0.0
        if s.kind == "water_flow":
            return lv.flow
        if s.kind == "water_volume":
            return lv.total_l
        vals = lv.values()
        if s.kind == "medium_moisture":
            return vals["moisture_b" if s.id.endswith("_b") else "moisture_a"]
        if s.kind == "moisture_raw":
            return vals["moisture_b_mv" if s.id.endswith("_b_mv") else "moisture_a_mv"]
        return vals.get(s.kind)
    rack_levels = [lv for (si, r, _), lv in levels.items() if si == site_id and r == s.rack]
    if s.kind == "leak":
        leaking = any(faults.get(f"{site_id}/{s.rack}-l{k[2]}") == "leak"
                      for k in levels if k[0] == site_id and k[1] == s.rack)
        return 1.0 if leaking and "floor" in s.id else 0.0
    if s.kind == "pump_current":
        return (2.4 if any(lv.valve for lv in rack_levels) else 0.05) + rng.gauss(0, 0.02)
    if s.kind == "wifi_rssi":
        return -66.0 + rng.gauss(0, 2)
    v = clim.get(s.kind)
    if v is None:
        return None
    # Rack-mounted air sensors: warmer and drier at the top, under the lights.
    if s.kind == "air_temperature" and s.id.endswith("_top"):
        v += 1.2
    elif s.kind == "air_temperature" and s.id.endswith("_bottom"):
        v -= 0.8
    elif s.kind == "relative_humidity" and s.id.endswith("_top"):
        v -= 4
    elif s.kind == "relative_humidity" and s.id.endswith("_bottom"):
        v += 3
    return v


if __name__ == "__main__":
    main()
