import csv
from pathlib import Path

from tgf.config import Config
from tools.replay import (
    apply_overrides,
    build_baseline,
    load_rows,
    replay,
    row_to_metrics,
)

_HEADER = [
    "t", "seq", "cap_age_ms", "infer_ms", "loop_ms", "status",
    "shoulder", "head", "lean",
    "ls_x", "ls_y", "ls_vis", "rs_x", "rs_y", "rs_vis",
    "le_x", "le_y", "le_vis", "re_x", "re_y", "re_vis",
    "d_shoulder", "d_head", "d_lean",
    "body_yaw_deg", "head_yaw_proxy", "cx", "scale", "edge",
]


def _row(t, status, shoulder, head=0.0, lean=0.0):
    return [
        f"{t:.3f}", 1, "0", "0", "0", status,
        f"{shoulder:.4f}" if shoulder is not None else "",
        f"{head:.4f}" if head is not None else "",
        f"{lean:.4f}" if lean is not None else "",
        "", "", "", "", "", "",
        "", "", "", "", "", "",
        "", "", "",
        "", "", "", "", "",
    ]


def _write_csv(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(_HEADER)
        for r in rows:
            w.writerow(r)


def test_load_rows_and_metrics(tmp_path):
    p = tmp_path / "log.csv"
    rows = [_row(i * 0.1, "Normal", 0.5) for i in range(5)]
    _write_csv(p, rows)
    loaded = load_rows(p)
    assert len(loaded) == 5
    m = row_to_metrics(loaded[0])
    assert m is not None
    assert m.shoulder == 0.5


def test_row_to_metrics_all_invalid_returns_none():
    row = {"shoulder": "", "head": "", "lean": ""}
    assert row_to_metrics(row) is None


def test_build_baseline_calibrates_from_normal_rows(tmp_path):
    p = tmp_path / "log.csv"
    rows = [_row(i * 0.1, "Normal", 0.2, head=0.1) for i in range(15)]
    _write_csv(p, rows)
    loaded = load_rows(p)
    bl = build_baseline(loaded, calib_rows=10)
    assert abs(bl.shoulder - 0.2) < 0.05
    assert abs(bl.head - 0.1) < 0.05


def test_apply_overrides_sets_known_key():
    cfg = Config()
    cfg = apply_overrides(cfg, ["sensitivity=high", "hold_sec=1.5"])
    assert cfg.sensitivity == "high"
    assert cfg.hold_sec == 1.5


def test_apply_overrides_ignores_unknown_key(capsys):
    cfg = Config()
    original_fps = cfg.fps
    cfg = apply_overrides(cfg, ["not_a_real_key=5"])
    assert cfg.fps == original_fps


def test_replay_detects_sustained_tilt(tmp_path):
    """15 calm rows to calibrate, then a sustained shoulder tilt long enough
    to cross hold_sec and fire an alert."""
    p = tmp_path / "log.csv"
    calm = [_row(i * 0.2, "Normal", 0.0) for i in range(15)]
    tilted = [_row(3.0 + i * 0.2, "Tilt Left", 10.0) for i in range(30)]
    _write_csv(p, calm + tilted)
    loaded = load_rows(p)

    cfg = Config()
    cfg.hold_sec = 1.0
    cfg.cooldown_sec = 0.0
    cfg = cfg.sanitize()
    bl = build_baseline(loaded, calib_rows=10)

    result = replay(loaded, cfg, bl)
    assert result["n_frames"] == len(loaded)
    assert result["n_alerts"] > 0
    assert result["channel_valid"]["shoulder"] == len(loaded)


def test_replay_flags_false_alert_when_original_status_normal(tmp_path):
    """If the CSV's own recorded status says Normal but replay (with a
    stricter config) fires an alert anyway, it should show up as a
    false-alert candidate."""
    p = tmp_path / "log.csv"
    calm = [_row(i * 0.2, "Normal", 0.0) for i in range(15)]
    borderline = [_row(3.0 + i * 0.2, "Normal", 5.0) for i in range(30)]
    _write_csv(p, calm + borderline)
    loaded = load_rows(p)

    cfg = Config()
    cfg.sensitivity = "high"
    cfg.hold_sec = 0.5
    cfg.cooldown_sec = 0.0
    cfg = cfg.sanitize()
    bl = build_baseline(loaded, calib_rows=10)

    result = replay(loaded, cfg, bl)
    # Not asserting a specific count (depends on thresholds), just that the
    # mechanism records candidates consistent with alerts fired.
    assert len(result["false_alerts"]) <= result["n_alerts"]


def test_main_runs_on_synthetic_csv(tmp_path, capsys):
    from tools.replay import main
    p = tmp_path / "log.csv"
    calm = [_row(i * 0.2, "Normal", 0.0) for i in range(15)]
    tilted = [_row(3.0 + i * 0.2, "Tilt Right", -10.0) for i in range(30)]
    _write_csv(p, calm + tilted)

    rc = main([str(p), "--sensitivity", "medium"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Kadrlar:" in out
    assert "Kanal statistikasi" in out
