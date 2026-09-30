"""Stage 9 tests: per-channel shoulder detection, compensation, visibility, noise."""
import math
import random

import pytest

from tgf.calibration import Baseline, Calibrator, CalibrationError, load_baseline, save_baseline
from tgf.config import Config
from tgf.geometry import Landmarks, Metrics, Point, compute_metrics
from tgf.monitor import PostureMonitor


# ── helpers ──────────────────────────────────────────────────────────────────

def _cfg(**kw) -> Config:
    c = Config(
        window=1, hold_sec=0.0,
        shoulder_deg=4.0, head_deg=6.0, neck_deg=5.0,
        left_factor=0.85, right_factor=1.0,
        exit_ratio=0.7, sensitivity="medium",
    )
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _bl(**kw) -> Baseline:
    b = Baseline(shoulder=0.0, head=0.0, lean=0.0, neck=0.0,
                 sigma_shoulder=0.1, sigma_head=0.1, sigma_neck=0.1)
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def _run(monitor, metrics_seq):
    """Feed a sequence of Metrics (or None) with integer timestamps."""
    states = []
    for i, m in enumerate(metrics_seq):
        states.append(monitor.update(m, float(i)))
    return states


# ── T1: shoulder-only +6° → Tilt Left ────────────────────────────────────────

def test_T1_shoulder_only_tilt_left():
    m = PostureMonitor(_cfg(), _bl())
    # shoulder=+6 >> thr(4*0.85=3.4), head=None, neck=None
    met = Metrics(shoulder=6.0, head=None, neck=None, lean=None)
    s = m.update(met, 0.0)
    assert s.status == "Tilt Left", f"Expected Tilt Left, got {s.status}"


# ── T2: shoulder +6°, head −5° (compensation) → still Tilt Left ──────────────

def test_T2_compensation_still_tilt_left():
    m = PostureMonitor(_cfg(), _bl())
    # shoulder contributes +6/3.4≈1.76, head contributes -5/6=−0.83 (normalized)
    # fused = (0.5*1.76 + 0.3*(−0.83)) / 0.8 ≈ (0.88 − 0.25)/0.8 ≈ 0.79
    # single_strong: shoulder ratio=1.76 >= 1.2 → trigger
    met = Metrics(shoulder=6.0, head=-5.0, neck=None, lean=None)
    s = m.update(met, 0.0)
    assert s.status == "Tilt Left", f"Expected Tilt Left, got {s.status}"


# ── T3: head-only +8° → Tilt Left ────────────────────────────────────────────

def test_T3_head_only_tilt_left():
    m = PostureMonitor(_cfg(), _bl())
    met = Metrics(shoulder=None, head=8.0, neck=None, lean=None)
    s = m.update(met, 0.0)
    assert s.status == "Tilt Left", f"Expected Tilt Left, got {s.status}"


# ── T4: shoulders low vis, head +8° → head channel works, no NoPose ──────────

def test_T4_low_shoulder_vis_head_works():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 0.2),   # vis < 0.35 → shoulder invalid
        right_shoulder=Point(0.5, 1.1, 0.2),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.4, 1.0),         # right ear lower → positive head roll
    )
    met = compute_metrics(lm, visibility_min=0.5, visibility_min_shoulder=0.35)
    assert met is not None, "Should not be None when ears are visible"
    assert met.shoulder is None, "Shoulder should be None (low vis)"
    assert met.head is not None, "Head should be valid"

    m = PostureMonitor(_cfg(), _bl())
    s = m.update(met, 0.0)
    assert s.status != "NoPose"


# ── T5: gaussian noise, no false alerts ──────────────────────────────────────

def test_T5_gaussian_noise_no_false_alerts():
    random.seed(42)
    sigma = 1.0
    cfg = _cfg(hold_sec=3.0)
    bl = _bl(sigma_shoulder=sigma, sigma_head=sigma, sigma_neck=sigma)
    m = PostureMonitor(cfg, bl)

    false_alerts = 0
    # 600 frames ≈ 10 min at 1 fps
    for i in range(600):
        met = Metrics(
            shoulder=random.gauss(0, sigma),
            head=random.gauss(0, sigma),
            neck=random.gauss(0, sigma),
            lean=random.gauss(0, 0.01),
        )
        s = m.update(met, float(i))
        if s.alert:
            false_alerts += 1

    assert false_alerts == 0, f"Got {false_alerts} false alerts with Gaussian noise"


# ── T6: left easier to trigger than right ────────────────────────────────────

def test_T6_left_triggers_before_right():
    """With left_factor=0.85 < right_factor=1.0, left threshold is lower."""
    cfg = _cfg(shoulder_deg=4.0, head_deg=6.0, left_factor=0.85, right_factor=1.0)
    bl = _bl(sigma_shoulder=0.1)
    # Symmetric positive and negative deltas of same magnitude
    mag = 5.0  # should trigger left (thr≈3.4) but not right (thr=4.0)

    m_left = PostureMonitor(cfg, bl)
    s_left = m_left.update(Metrics(shoulder=mag, head=None, neck=None, lean=None), 0.0)

    m_right = PostureMonitor(cfg, bl)
    s_right = m_right.update(Metrics(shoulder=-mag, head=None, neck=None, lean=None), 0.0)

    assert s_left.status == "Tilt Left", f"Left: {s_left.status}"
    # right_threshold = 4.0 * 1.0 * 1.0 = 4.0; mag=5.0 > 4.0 so also triggers
    # just verify left triggers at lower mag
    m_left2 = PostureMonitor(cfg, bl)
    s_low = m_left2.update(Metrics(shoulder=3.5, head=None, neck=None, lean=None), 0.0)
    m_right2 = PostureMonitor(cfg, bl)
    s_right_low = m_right2.update(Metrics(shoulder=-3.5, head=None, neck=None, lean=None), 0.0)
    assert s_low.status == "Tilt Left"   # 3.5 > left_thr≈3.4
    assert s_right_low.status == "Normal"  # 3.5 < right_thr=4.0


# ── T7: old calibration.json (no sigma) loads with defaults ──────────────────

def test_T7_old_calibration_json_loads(tmp_path):
    import json
    p = tmp_path / "calibration.json"
    p.write_text(json.dumps({"shoulder": 1.5, "head": -0.5, "lean": 0.02}))
    bl = load_baseline(p)
    assert bl is not None
    assert bl.shoulder == pytest.approx(1.5)
    assert bl.sigma_shoulder == pytest.approx(1.0)  # default
    assert bl.sigma_head == pytest.approx(1.0)


# ── geometry: compute_metrics per-channel ────────────────────────────────────

def test_compute_metrics_all_valid():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 1.0),
        right_shoulder=Point(0.5, 1.0, 1.0),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )
    m = compute_metrics(lm)
    assert m is not None
    assert m.shoulder is not None
    assert m.head is not None
    assert m.neck is not None


def test_compute_metrics_ears_only():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 0.1),
        right_shoulder=Point(0.5, 1.0, 0.1),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )
    m = compute_metrics(lm, visibility_min=0.5, visibility_min_shoulder=0.35)
    assert m is not None
    assert m.shoulder is None
    assert m.head is not None
    assert m.neck is None


def test_compute_metrics_all_invisible_is_none():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 0.1),
        right_shoulder=Point(0.5, 1.0, 0.1),
        left_ear=Point(-0.2, 0.0, 0.1),
        right_ear=Point(0.2, 0.0, 0.1),
    )
    m = compute_metrics(lm, visibility_min=0.5, visibility_min_shoulder=0.35)
    assert m is None


# ── calibration: sigma and outlier filtering ─────────────────────────────────

def test_calibrator_sigma_computed():
    cal = Calibrator(min_samples=10)
    for i in range(20):
        cal.add(Metrics(shoulder=float(i % 3), head=0.0, neck=0.0, lean=0.0))
    bl = cal.result()
    assert bl.sigma_shoulder > 0


def test_calibrator_movement_raises():
    cal = Calibrator(min_samples=5)
    # Very high variance = user moving
    for i in range(10):
        cal.add(Metrics(shoulder=float(i * 3), head=0.0, neck=0.0, lean=0.0))
    with pytest.raises(CalibrationError, match="Qimirlamay"):
        cal.result()


def test_calibrator_save_load_roundtrip(tmp_path):
    cal = Calibrator(min_samples=5)
    for _ in range(10):
        cal.add(Metrics(shoulder=1.0, head=0.5, neck=0.2, lean=0.01))
    bl = cal.result()
    p = tmp_path / "calibration.json"
    save_baseline(bl, p)
    loaded = load_baseline(p)
    assert loaded is not None
    assert loaded.shoulder == pytest.approx(bl.shoulder)
    assert loaded.sigma_shoulder == pytest.approx(bl.sigma_shoulder)
