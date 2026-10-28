import pytest

from agria.derived import DliIntegrator, local_midnight, vpd_kpa


def test_vpd_reference_values():
    # SVP at 25 °C is ~3.168 kPa
    assert vpd_kpa(25, 50) == pytest.approx(1.584, abs=0.005)
    assert vpd_kpa(20, 100) == 0
    assert vpd_kpa(20, 0) == pytest.approx(2.338, abs=0.005)


def test_dli_constant_light_one_hour():
    tz = "America/New_York"
    start = local_midnight(1_760_000_000, tz) + 10 * 3600
    d = DliIntegrator(tz)
    for i in range(0, 3601, 30):
        total = d.add(start + i, 500.0)
    # 500 µmol/m²/s for 3600 s = 1.8 mol/m²
    assert total == pytest.approx(1.8, rel=1e-6)


def test_dli_resets_at_midnight_and_skips_gaps():
    tz = "America/New_York"
    m = local_midnight(1_760_000_000, tz)
    d = DliIntegrator(tz, max_gap_s=600)
    d.add(m - 60, 100)
    d.add(m - 30, 100)
    assert d.add(m + 30, 100) == 0.0  # new day, no carry-over
    assert d.add(m + 30 + 3600, 100) == 0.0  # gap too long to bridge
