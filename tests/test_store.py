from agria.store import Store


def test_history_buckets_and_retention_rollup():
    s = Store(":memory:")
    now = 1_760_000_000.0
    for i in range(0, 120 * 86400, 600):  # 120 days, every 10 min
        s.add_reading("k", now - 120 * 86400 + i, float(i % 7))
    removed = s.apply_retention(90, now=now)
    assert removed > 0
    first = s._query("SELECT MIN(ts) t FROM readings")[0]["t"]
    assert first >= now - 90 * 86400 - 3600
    hist = s.history("k", now - 120 * 86400, now, points=200)
    assert hist and hist[0]["ts"] < first  # old range served from hourly rollup
    assert all(h["min"] <= h["mean"] <= h["max"] for h in hist)
    # Re-running retention is idempotent.
    assert s.apply_retention(90, now=now) == 0
