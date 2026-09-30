import json
from math import cos, radians, sin

from tgf.config import Config
from tgf.filters import MovingAverage
from tgf.geometry import (
    Landmarks,
    Landmarks3D,
    Point,
    Point3D,
    compute_metrics,
    lean_ratio,
    roll_deg,
)


def test_roll_positive_left_lower():
    # image coords: larger y = lower on screen
    left = Point(0.0, -0.5, 1.0)
    right = Point(1.0, 0.5, 1.0)
    assert roll_deg(left, right) > 0


def test_roll_negative_right_lower():
    left = Point(0.0, 0.5, 1.0)
    right = Point(1.0, -0.5, 1.0)
    assert roll_deg(left, right) < 0


def test_roll_horizontal_zero():
    left = Point(0.0, 0.5, 1.0)
    right = Point(1.0, 0.5, 1.0)
    assert roll_deg(left, right) == 0.0


def test_roll_angle_in_range():
    left = Point(0.0, 5.0, 1.0)
    right = Point(0.01, -5.0, 1.0)
    v = roll_deg(left, right)
    assert -90.0 < v <= 90.0


def test_lean_ratio_sign_left():
    l_ear = Point(-0.2, 0.0, 1.0)
    r_ear = Point(0.0, 0.0, 1.0)
    l_sh = Point(-0.5, 1.0, 1.0)
    r_sh = Point(0.5, 1.0, 1.0)
    assert lean_ratio(l_ear, r_ear, l_sh, r_sh) < 0


def test_lean_ratio_scale_invariance():
    l_ear = Point(-0.2, 0.0, 1.0)
    r_ear = Point(0.2, 0.0, 1.0)
    l_sh = Point(-0.5, 1.0, 1.0)
    r_sh = Point(0.5, 1.0, 1.0)
    base = lean_ratio(l_ear, r_ear, l_sh, r_sh)
    scaled = lean_ratio(
        Point(l_ear.x * 2, l_ear.y, 1.0),
        Point(r_ear.x * 2, r_ear.y, 1.0),
        Point(l_sh.x * 2, l_sh.y, 1.0),
        Point(r_sh.x * 2, r_sh.y, 1.0),
    )
    assert abs(base - scaled) < 1e-9


def test_compute_metrics_low_visibility_none():
    # Stage 9: now returns None only if ALL channels invalid.
    # With ears visible (vis=1.0), head channel is valid even if shoulders are low.
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 0.1),
        right_shoulder=Point(0.5, 1.0, 1.0),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )
    m = compute_metrics(lm, visibility_min=0.5, visibility_min_shoulder=0.35)
    # shoulder None (one side < 0.35), head valid
    assert m is not None
    assert m.head is not None
    assert m.shoulder is None  # left_shoulder vis=0.1 < 0.35


def test_compute_metrics_ok():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 1.0),
        right_shoulder=Point(0.5, 1.0, 1.0),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )
    m = compute_metrics(lm, visibility_min=0.5)
    assert m is not None
    assert m.shoulder == 0.0


def _yaw_rotate(p: Point3D, yaw_deg: float) -> Point3D:
    """Rotate a 3D point about the vertical (Y) axis by yaw_deg (camera-aligned
    axes: X right, Y down, Z toward camera)."""
    a = radians(yaw_deg)
    x = p.x * cos(a) + p.z * sin(a)
    z = -p.x * sin(a) + p.z * cos(a)
    return Point3D(x, p.y, z)


def test_shoulder_yaw_invariant_stable_across_body_yaw():
    """Same real shoulder tilt, projected at different body-yaw angles, should
    yield near-identical shoulder_yaw_invariant (within 2 degrees)."""
    # A real, fixed left-lower shoulder tilt: left shoulder slightly higher in y
    # (image y grows downward; here we work directly in 3D world space).
    base_left = Point3D(-0.2, -0.05, 0.0)
    base_right = Point3D(0.2, 0.05, 0.0)
    base_l_ear = Point3D(-0.08, -0.35, 0.05)
    base_r_ear = Point3D(0.08, -0.35, 0.05)

    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 1.0),
        right_shoulder=Point(0.5, 1.0, 1.0),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )

    values = []
    for yaw in (0.0, 20.0, 40.0, -30.0):
        lm3 = Landmarks3D(
            nose=Point3D(0.0, -0.4, 0.1),
            left_shoulder=_yaw_rotate(base_left, yaw),
            right_shoulder=_yaw_rotate(base_right, yaw),
            left_ear=_yaw_rotate(base_l_ear, yaw),
            right_ear=_yaw_rotate(base_r_ear, yaw),
        )
        m = compute_metrics(lm, visibility_min=0.5, lm3=lm3)
        assert m is not None
        assert m.shoulder_yaw_invariant is not None
        values.append(m.shoulder_yaw_invariant)

    assert max(values) - min(values) < 2.0


def test_compute_metrics_without_lm3_leaves_yaw_invariant_none():
    lm = Landmarks(
        left_shoulder=Point(-0.5, 1.0, 1.0),
        right_shoulder=Point(0.5, 1.0, 1.0),
        left_ear=Point(-0.2, 0.0, 1.0),
        right_ear=Point(0.2, 0.0, 1.0),
    )
    m = compute_metrics(lm, visibility_min=0.5)
    assert m is not None
    assert m.shoulder_yaw_invariant is None
    assert m.neck_yaw_invariant is None


def test_moving_average_values():
    ma = MovingAverage(3)
    assert ma.update(1.0) == 1.0
    assert ma.update(2.0) == 1.5
    assert ma.update(3.0) == 2.0
    assert ma.update(6.0) == (2.0 + 3.0 + 6.0) / 3


def test_config_load_save_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(fps=15, camera_index=1)
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.fps == 15
    assert loaded.camera_index == 1


def test_config_load_missing_file_defaults(tmp_path):
    path = tmp_path / "missing.json"
    loaded = Config.load(path)
    assert loaded == Config()


def test_config_load_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"fps": 20, "bogus_key": 123}))
    loaded = Config.load(path)
    assert loaded.fps == 20
