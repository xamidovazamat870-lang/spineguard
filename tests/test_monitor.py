from tgf.calibration import Baseline
from tgf.config import Config
from tgf.geometry import Metrics
from tgf.monitor import PostureMonitor


def _cfg(**overrides) -> Config:
    c = Config(window=1, enter_deg=7.0, exit_deg=5.0, left_threshold=6.0, right_threshold=8.0, hold_sec=3.0)
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _baseline() -> Baseline:
    return Baseline(shoulder=0.0, head=0.0, lean=0.0, neck=0.0, sigma_shoulder=0.1, sigma_head=0.1, sigma_neck=0.1)


def test_normal_no_tilt():
    m = PostureMonitor(_cfg(), _baseline())
    s = m.update(Metrics(shoulder=1.0, head=1.0, neck=None, lean=0.0), now=0.0)
    assert s.status == "Normal"
    assert s.alert is False


def test_left_tilt_detected():
    m = PostureMonitor(_cfg(), _baseline())
    s = m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    assert s.status == "Tilt Left"


def test_right_tilt_detected():
    m = PostureMonitor(_cfg(), _baseline())
    s = m.update(Metrics(shoulder=-5.0, head=-5.0, neck=None, lean=0.0), now=0.0)
    assert s.status == "Tilt Right"


def test_no_alert_before_hold_sec():
    m = PostureMonitor(_cfg(), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    s = m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=2.0)
    assert s.status == "Tilt Left"
    assert s.alert is False


def test_alert_after_hold_sec():
    m = PostureMonitor(_cfg(), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    s = m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=3.5)
    assert s.status == "Tilt Left"
    assert s.alert is True


def test_hysteresis_exit():
    m = PostureMonitor(_cfg(), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    s = m.update(Metrics(shoulder=1.0, head=1.0, neck=None, lean=0.0), now=1.0)
    assert s.status == "Normal"


def test_hysteresis_stays_tilted_in_deadband():
    m = PostureMonitor(_cfg(), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    s = m.update(Metrics(shoulder=3.0, head=3.0, neck=None, lean=0.0), now=1.0)
    assert s.status == "Tilt Left"


def test_nopose_resets_timer():
    m = PostureMonitor(_cfg(nopose_grace_sec=0.0), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    s = m.update(None, now=1.0)
    assert s.status == "NoPose"
    s2 = m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=1.1)
    assert s2.status == "Tilt Left"
    s3 = m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=3.5)
    assert s3.alert is False


def test_brief_dropout_does_not_reset_hold_timer():
    m = PostureMonitor(_cfg(), _baseline())
    tilt = Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0)
    m.update(tilt, now=0.0)
    s = m.update(None, now=1.0)  # within grace: status held, no alert
    assert s.status == "Tilt Left" and s.alert is False
    m.update(tilt, now=1.1)
    s = m.update(tilt, now=3.5)
    assert s.alert is True


def test_long_dropout_becomes_nopose_and_clears_filters():
    m = PostureMonitor(_cfg(window=4), _baseline())
    m.update(Metrics(shoulder=5.0, head=5.0, neck=None, lean=0.0), now=0.0)
    m.update(None, now=1.0)
    assert m.update(None, now=3.0).status == "NoPose"
    s = m.update(Metrics(shoulder=0.0, head=0.0, neck=None, lean=0.0), now=3.1)
    assert s.status == "Normal"  # stale tilt samples must not leak in
