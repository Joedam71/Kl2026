from agria.alerts import Severity, ThresholdState
from agria.config import Thresholds

T = Thresholds(alarm_low=5.0, warn_low=5.5, warn_high=6.5, alarm_high=7.0, hysteresis=0.1, delay_s=60)


def test_debounce_requires_sustained_excursion():
    s = ThresholdState()
    assert not s.step(6.6, 0, T)
    assert not s.step(6.0, 30, T)  # back in band resets the timer
    assert not s.step(6.6, 40, T)
    assert not s.step(6.6, 90, T)
    assert s.step(6.6, 100, T) and s.level == Severity.WARN and s.limit == "warn_high"


def test_escalates_to_alarm_on_its_own_timer():
    s = ThresholdState()
    s.step(6.6, 0, T)
    s.step(6.6, 60, T)
    assert s.level == Severity.WARN
    assert not s.step(7.2, 70, T)
    assert s.step(7.2, 130, T) and s.level == Severity.ALARM


def test_hysteresis_on_clear():
    s = ThresholdState()
    s.step(6.6, 0, T)
    s.step(6.6, 60, T)
    assert not s.step(6.45, 70, T)  # inside band but not by 0.1
    assert s.step(6.35, 80, T) and s.level == Severity.OK


def test_alarm_steps_down_to_warn():
    s = ThresholdState()
    s.step(7.5, 0, T)
    s.step(7.5, 60, T)
    assert s.level == Severity.ALARM
    assert s.step(6.7, 70, T) and s.level == Severity.WARN
