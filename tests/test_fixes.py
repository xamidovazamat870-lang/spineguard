import json
import math

from tgf.cli import _load_baseline, _save_baseline
from tgf.calibration import Baseline
from tgf.config import Config
from tgf.geometry import Point, roll_deg
from tgf.paths import baseline_path_for, home_dir


def test_roll_uses_pixel_aspect():
    # 4:3 frame, true 10deg tilt: dx=0.5*4/3 units of height, dy = tan(10)*dx
    aspect = 4 / 3
    dx_px = 0.5 * aspect
    dy_px = math.tan(math.radians(10)) * dx_px
    # normalized coords: x/width, y/height with height=1 unit, width=aspect units
    left = Point(0.0, dy_px, 1.0)
    right = Point(-dx_px / aspect, 0.0, 1.0)
    assert abs(roll_deg(left, right, aspect) - 10.0) < 1e-6
    assert abs(roll_deg(left, right) - 10.0) > 2.0  # old behaviour was inflated


def test_config_sanitize_bad_values(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"fps": "abc", "window": 0, "enter_deg": 4, "exit_deg": 9, "camera_index": -3}))
    c = Config.load(p)
    assert c.fps == 8 and c.window == 1 and c.camera_index == 0
    assert c.exit_deg <= c.enter_deg


def test_config_deprecated_keys_warn_once(tmp_path, capsys):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"enter_deg": 4, "left_threshold": 6}))
    c = Config.load(p)
    err = capsys.readouterr().err
    assert "eskirgan" in err
    assert "enter_deg" in err and "left_threshold" in err
    assert c.shoulder_deg == Config().shoulder_deg  # deprecated keys ignored in logic


def test_config_no_warning_without_deprecated_keys(tmp_path, capsys):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"fps": 10}))
    Config.load(p)
    err = capsys.readouterr().err
    assert err == ""


def test_config_non_dict_json(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("[1,2,3]")
    assert Config.load(p) == Config()


def test_baseline_roundtrip_and_corrupt(tmp_path):
    p = tmp_path / "calibration.json"
    _save_baseline(Baseline(1.0, 2.0, 0.1), p)
    assert _load_baseline(p) == Baseline(1.0, 2.0, 0.1)
    p.write_text("[1,2]")
    assert _load_baseline(p) is None
    p.write_text('{"shoulder": "x", "head": 1, "lean": 1}')
    assert _load_baseline(p) is None


def test_channels_isolated(monkeypatch, tmp_path):
    monkeypatch.delenv("TGF_HOME", raising=False)
    monkeypatch.setenv("TGF_CHANNEL", "dev")
    assert home_dir().name == ".tgf-dev"
    monkeypatch.setenv("TGF_CHANNEL", "stable")
    assert home_dir().name == ".tgf"
    assert baseline_path_for(tmp_path / "x" / "config.json") == tmp_path / "x" / "calibration.json"
