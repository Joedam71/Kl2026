"""SQLite storage for readings, alerts, calibrations and camera images.

SQLite is deliberate for the pilot (one instrumented rack plus site
climate, ~60 sensors at 30 s, about 170k rows/day). Raw rows are kept
``raw_days`` and then rolled up to hourly mean/min/max. Move to TimescaleDB
at Phase 3 scale-out; everything goes through this class, so that is a
contained change.

Crop-cycle records deliberately hold NO medium formulation or inoculation
recipe data. Batches are identified by an opaque batch ID; the formula
lives in a separate restricted system (see docs/DATA_MODEL.md).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    sensor_key TEXT NOT NULL,
    ts REAL NOT NULL,
    value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_key_ts ON readings(sensor_key, ts);

CREATE TABLE IF NOT EXISTS readings_hourly (
    sensor_key TEXT NOT NULL,
    hour_ts INTEGER NOT NULL,
    n INTEGER NOT NULL,
    mean REAL NOT NULL,
    min REAL NOT NULL,
    max REAL NOT NULL,
    PRIMARY KEY (sensor_key, hour_ts)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    site TEXT NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    value REAL,
    raised_ts REAL NOT NULL,
    cleared_ts REAL,
    acked_ts REAL,
    acked_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(cleared_ts);

CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_key TEXT NOT NULL,
    ts REAL NOT NULL,
    by TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_cal_key ON calibrations(sensor_key, ts);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    camera TEXT NOT NULL,
    ts REAL NOT NULL,
    path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images ON images(site, camera, ts);

CREATE TABLE IF NOT EXISTS irrigation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    zone TEXT NOT NULL,
    rack TEXT NOT NULL,
    level INTEGER NOT NULL,
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    liters REAL NOT NULL,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_irr ON irrigation_events(site, zone, end_ts);

CREATE TABLE IF NOT EXISTS media_batches (
    id TEXT PRIMARY KEY,
    received_ts REAL,
    notes TEXT,
    created_ts REAL NOT NULL,
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS crop_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    rack TEXT NOT NULL,
    level INTEGER NOT NULL,
    batch_id TEXT,
    inoculation_ts REAL,
    variety TEXT NOT NULL,
    irrigation_mode TEXT NOT NULL,
    stage TEXT,
    start_ts REAL NOT NULL,
    end_ts REAL,
    yield_g REAL,
    notes TEXT,
    created_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_cycles ON crop_cycles(site, rack, level, end_ts);

CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id INTEGER NOT NULL REFERENCES crop_cycles(id),
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    notes TEXT,
    by TEXT
);
CREATE INDEX IF NOT EXISTS idx_interventions ON interventions(cycle_id, ts);
"""


class Store:
    def __init__(self, path: str | Path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.executescript(SCHEMA)
            self._db.commit()

    def close(self):
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, args=()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, args)
            self._db.commit()
            return cur

    def _query(self, sql: str, args=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    # readings

    def add_reading(self, key: str, ts: float, value: float):
        self._exec("INSERT INTO readings(sensor_key, ts, value) VALUES (?,?,?)", (key, ts, value))

    def latest_readings(self) -> dict[str, tuple[float, float]]:
        rows = self._query(
            "SELECT r.sensor_key, r.ts, r.value FROM readings r "
            "JOIN (SELECT sensor_key, MAX(ts) AS ts FROM readings GROUP BY sensor_key) m "
            "ON r.sensor_key = m.sensor_key AND r.ts = m.ts"
        )
        return {r["sensor_key"]: (r["ts"], r["value"]) for r in rows}

    def readings_since(self, key: str, start: float) -> list[tuple[float, float]]:
        rows = self._query("SELECT ts, value FROM readings WHERE sensor_key=? AND ts>=? ORDER BY ts", (key, start))
        return [(r["ts"], r["value"]) for r in rows]

    def history(self, key: str, start: float, end: float, points: int = 300) -> list[dict]:
        """Bucketed history (mean/min/max per bucket), spanning raw and hourly tables."""
        points = max(1, min(points, 5000))
        bucket = max(1.0, (end - start) / points)
        first_raw = self._query("SELECT MIN(ts) AS t FROM readings WHERE sensor_key=?", (key,))[0]["t"]
        raw_start = start if first_raw is None else max(start, first_raw)
        out: list[dict] = []
        if first_raw is None or start < first_raw:
            hourly_end = end if first_raw is None else min(end, first_raw)
            b = max(bucket, 3600.0)
            rows = self._query(
                "SELECT CAST(hour_ts / ? AS INTEGER) * ? AS b, SUM(mean*n)/SUM(n) AS mean, MIN(min) AS min, MAX(max) AS max "
                "FROM readings_hourly WHERE sensor_key=? AND hour_ts>=? AND hour_ts<? GROUP BY b ORDER BY b",
                (b, b, key, start, hourly_end),
            )
            out += [dict(r) for r in rows]
        if first_raw is not None:
            rows = self._query(
                "SELECT CAST(ts / ? AS INTEGER) * ? AS b, AVG(value) AS mean, MIN(value) AS min, MAX(value) AS max "
                "FROM readings WHERE sensor_key=? AND ts>=? AND ts<=? GROUP BY b ORDER BY b",
                (bucket, bucket, key, raw_start, end),
            )
            out += [dict(r) for r in rows]
        return [{"ts": r["b"], "mean": r["mean"], "min": r["min"], "max": r["max"]} for r in out]

    def apply_retention(self, raw_days: int, now: float | None = None) -> int:
        now = time.time() if now is None else now
        cutoff = int((now - raw_days * 86400) // 3600 * 3600)  # whole hours only
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO readings_hourly(sensor_key, hour_ts, n, mean, min, max) "
                "SELECT sensor_key, CAST(ts / 3600 AS INTEGER) * 3600, COUNT(*), AVG(value), MIN(value), MAX(value) "
                "FROM readings WHERE ts < ? GROUP BY 1, 2",
                (cutoff,),
            )
            n = self._db.execute("DELETE FROM readings WHERE ts < ?", (cutoff,)).rowcount
            self._db.commit()
        return n

    # alerts

    def add_alert(self, key, site, kind, severity, message, value, ts) -> int:
        cur = self._exec(
            "INSERT INTO alerts(key, site, kind, severity, message, value, raised_ts) VALUES (?,?,?,?,?,?,?)",
            (key, site, kind, severity, message, value, ts),
        )
        return cur.lastrowid

    def clear_alert(self, alert_id: int, ts: float):
        self._exec("UPDATE alerts SET cleared_ts=? WHERE id=? AND cleared_ts IS NULL", (ts, alert_id))

    def ack_alert(self, alert_id: int, by: str, ts: float) -> bool:
        cur = self._exec("UPDATE alerts SET acked_ts=?, acked_by=? WHERE id=? AND acked_ts IS NULL", (ts, by, alert_id))
        return cur.rowcount > 0

    def alerts(self, active_only: bool = False, limit: int = 200) -> list[dict]:
        where = "WHERE cleared_ts IS NULL" if active_only else ""
        rows = self._query(f"SELECT * FROM alerts {where} ORDER BY raised_ts DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # calibrations

    def add_calibration(self, key: str, ts: float, by: str | None, notes: str | None) -> int:
        return self._exec("INSERT INTO calibrations(sensor_key, ts, by, notes) VALUES (?,?,?,?)", (key, ts, by, notes)).lastrowid

    def last_calibrations(self) -> dict[str, dict]:
        rows = self._query(
            "SELECT c.* FROM calibrations c JOIN (SELECT sensor_key, MAX(ts) AS ts FROM calibrations GROUP BY sensor_key) m "
            "ON c.sensor_key = m.sensor_key AND c.ts = m.ts"
        )
        return {r["sensor_key"]: dict(r) for r in rows}

    def calibrations(self, key: str | None = None, limit: int = 200) -> list[dict]:
        if key:
            rows = self._query("SELECT * FROM calibrations WHERE sensor_key=? ORDER BY ts DESC LIMIT ?", (key, limit))
        else:
            rows = self._query("SELECT * FROM calibrations ORDER BY ts DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # images

    def add_image(self, site: str, camera: str, ts: float, path: str):
        self._exec("INSERT INTO images(site, camera, ts, path) VALUES (?,?,?,?)", (site, camera, ts, path))

    def latest_image(self, site: str, camera: str) -> dict | None:
        rows = self._query("SELECT * FROM images WHERE site=? AND camera=? ORDER BY ts DESC LIMIT 1", (site, camera))
        return dict(rows[0]) if rows else None

    # irrigation events

    def add_irrigation_event(self, site, zone, rack, level, start_ts, end_ts, liters, source) -> int:
        return self._exec(
            "INSERT INTO irrigation_events(site, zone, rack, level, start_ts, end_ts, liters, source) "
            "VALUES (?,?,?,?,?,?,?,?)", (site, zone, rack, level, start_ts, end_ts, liters, source)).lastrowid

    def irrigation_events(self, site: str | None = None, zone: str | None = None, since: float | None = None,
                          limit: int = 500) -> list[dict]:
        where, args = [], []
        for col, val in (("site", site), ("zone", zone)):
            if val is not None:
                where.append(f"{col}=?")
                args.append(val)
        if since is not None:
            where.append("end_ts>=?")
            args.append(since)
        sql = "SELECT * FROM irrigation_events" + (" WHERE " + " AND ".join(where) if where else "")
        rows = self._query(sql + " ORDER BY end_ts DESC LIMIT ?", (*args, limit))
        return [dict(r) for r in rows]

    def irrigation_liters(self, site: str, zone: str, start: float, end: float) -> float:
        row = self._query("SELECT COALESCE(SUM(liters), 0) AS l FROM irrigation_events "
                          "WHERE site=? AND zone=? AND start_ts>=? AND start_ts<?", (site, zone, start, end))[0]
        return float(row["l"])

    # media batches (opaque IDs only; no formulation data)

    def add_batch(self, batch_id: str, received_ts: float | None, notes: str | None, by: str | None, ts: float):
        self._exec("INSERT INTO media_batches(id, received_ts, notes, created_ts, created_by) VALUES (?,?,?,?,?)",
                   (batch_id, received_ts, notes, ts, by))

    def batches(self) -> list[dict]:
        return [dict(r) for r in self._query("SELECT * FROM media_batches ORDER BY created_ts DESC")]

    def batch(self, batch_id: str) -> dict | None:
        rows = self._query("SELECT * FROM media_batches WHERE id=?", (batch_id,))
        return dict(rows[0]) if rows else None

    # crop cycles

    def add_cycle(self, **f) -> int:
        cols = ("site", "rack", "level", "batch_id", "inoculation_ts", "variety", "irrigation_mode",
                "stage", "start_ts", "notes", "created_by")
        return self._exec(f"INSERT INTO crop_cycles({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                          tuple(f.get(c) for c in cols)).lastrowid

    def cycle(self, cycle_id: int) -> dict | None:
        rows = self._query("SELECT * FROM crop_cycles WHERE id=?", (cycle_id,))
        return dict(rows[0]) if rows else None

    def cycles(self, site: str | None = None, active: bool | None = None, limit: int = 500) -> list[dict]:
        where, args = [], []
        if site:
            where.append("site=?")
            args.append(site)
        if active is True:
            where.append("end_ts IS NULL")
        elif active is False:
            where.append("end_ts IS NOT NULL")
        sql = "SELECT * FROM crop_cycles" + (" WHERE " + " AND ".join(where) if where else "")
        return [dict(r) for r in self._query(sql + " ORDER BY start_ts DESC LIMIT ?", (*args, limit))]

    def active_cycle(self, site: str, rack: str, level: int) -> dict | None:
        rows = self._query("SELECT * FROM crop_cycles WHERE site=? AND rack=? AND level=? AND end_ts IS NULL",
                           (site, rack, level))
        return dict(rows[0]) if rows else None

    def update_cycle(self, cycle_id: int, **fields):
        allowed = {"stage", "notes", "end_ts", "yield_g", "irrigation_mode"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if sets:
            self._exec(f"UPDATE crop_cycles SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?",
                       (*sets.values(), cycle_id))

    def add_intervention(self, cycle_id: int, ts: float, kind: str, notes: str | None, by: str | None) -> int:
        return self._exec("INSERT INTO interventions(cycle_id, ts, kind, notes, by) VALUES (?,?,?,?,?)",
                          (cycle_id, ts, kind, notes, by)).lastrowid

    def interventions(self, cycle_id: int) -> list[dict]:
        return [dict(r) for r in self._query("SELECT * FROM interventions WHERE cycle_id=? ORDER BY ts", (cycle_id,))]

    # export

    def raw_readings(self, keys: list[str], start: float, end: float):
        if not keys:
            return []
        q = ",".join("?" * len(keys))
        return self._query(f"SELECT sensor_key, ts, value FROM readings WHERE sensor_key IN ({q}) "
                           f"AND ts>=? AND ts<=? ORDER BY ts", (*keys, start, end))
