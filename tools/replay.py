"""Replay a `--log` CSV through Metrics -> PostureMonitor without camera/mediapipe.

Usage:
    python -m tools.replay LOG.csv [--set key=val ...] [--sensitivity low|medium|high]
                                    [--baseline PATH] [--calib-rows N]

Reads the raw per-channel metrics already present in the CSV (written by
`tgf/cli.py`'s `--log`), rebuilds a `Config`/`Baseline`/`PostureMonitor`, and
re-runs them through `PostureMonitor.update()` frame by frame. Prints:
  - an alert timeline (t, side, reason)
  - a false-alert estimate (alerts fired while the *original* logged status
    was "Normal" -- i.e. the recorded run considered the frame fine)
  - channel stats: how many frames had each channel valid, and which channel
    was cited (`reason`) for each alert.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import fields
from pathlib import Path
from typing import Optional

from tgf.calibration import Baseline, Calibrator, CalibrationError
from tgf.config import Config
from tgf.geometry import Metrics
from tgf.monitor import PostureMonitor, State


def _parse_float(v: str) -> Optional[float]:
    v = v.strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict]:
    """Read the replay CSV; skips rows that don't parse as a data row."""
    rows: list[dict] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows.append(raw)
    return rows


def row_to_metrics(row: dict) -> Optional[Metrics]:
    shoulder = _parse_float(row.get("shoulder", ""))
    head = _parse_float(row.get("head", ""))
    lean = _parse_float(row.get("lean", ""))
    if shoulder is None and head is None:
        return None
    # CSV (Stage 8/10) has no `neck` column; approximate it as unavailable
    # unless both shoulder and head are present (matches compute_metrics'
    # neck_ok = sh_ok and ear_ok gate closely enough for replay purposes).
    neck = None
    return Metrics(shoulder=shoulder, head=head, neck=neck, lean=lean)


def apply_overrides(cfg: Config, overrides: list[str]) -> Config:
    valid = {f.name for f in fields(Config)}
    for item in overrides:
        if "=" not in item:
            print(f"e'tiborsiz qoldirildi (key=val emas): {item}", file=sys.stderr)
            continue
        k, v = item.split("=", 1)
        k = k.strip()
        if k not in valid:
            print(f"noma'lum config kaliti: {k}", file=sys.stderr)
            continue
        default = getattr(cfg, k)
        try:
            if isinstance(default, bool):
                setattr(cfg, k, v.strip().lower() in ("1", "true", "yes", "on"))
            else:
                setattr(cfg, k, type(default)(v))
        except (TypeError, ValueError):
            print(f"noto'g'ri qiymat {k}={v}", file=sys.stderr)
    return cfg.sanitize()


def build_baseline(rows: list[dict], calib_rows: int) -> Baseline:
    """Calibrate from the first `calib_rows` Normal-status frames in the log."""
    calibrator = Calibrator(min_samples=min(10, max(1, calib_rows)))
    used = 0
    for row in rows:
        if used >= calib_rows:
            break
        if row.get("status") not in ("Normal", ""):
            continue
        m = row_to_metrics(row)
        if m is None:
            continue
        calibrator.add(m)
        used += 1
    try:
        return calibrator.result()
    except CalibrationError:
        # Fall back to a neutral baseline so replay can still run (report
        # this loudly -- the estimated thresholds will be off).
        print("Ogohlantirish: avtomatik kalibratsiya muvaffaqiyatsiz "
              "(yetarli 'Normal' namuna yo'q); neytral baseline ishlatiladi.",
              file=sys.stderr)
        return Baseline(shoulder=0.0, head=0.0, lean=0.0, neck=0.0)


def replay(rows: list[dict], cfg: Config, baseline: Baseline) -> dict:
    monitor = PostureMonitor(cfg, baseline)
    timeline: list[tuple[str, str, str]] = []  # (t, status, reason)
    false_alerts: list[tuple[str, str]] = []   # (t, reason) alert fired while original log said Normal
    channel_valid = {"shoulder": 0, "head": 0, "lean": 0}
    channel_alert_count: dict[str, int] = {}
    n_frames = 0
    n_alerts = 0

    t0: Optional[float] = None
    for row in rows:
        t_raw = _parse_float(row.get("t", ""))
        t = t_raw if t_raw is not None else float(n_frames)
        if t0 is None:
            t0 = t
        rel_t = t - t0

        m = row_to_metrics(row)
        for ch in ("shoulder", "head", "lean"):
            if m is not None and getattr(m, ch) is not None:
                channel_valid[ch] += 1

        state: State = monitor.update(m, now=t)
        n_frames += 1

        if state.alert:
            n_alerts += 1
            side = "left" if state.status == "Tilt Left" else "right" if state.status == "Tilt Right" else "?"
            timeline.append((f"{rel_t:.2f}", side, state.reason or ""))
            for ch in (state.reason or "").split("+"):
                ch = ch.strip()
                if ch:
                    channel_alert_count[ch] = channel_alert_count.get(ch, 0) + 1
            original_status = row.get("status", "")
            if original_status == "Normal":
                false_alerts.append((f"{rel_t:.2f}", state.reason or ""))

    return {
        "n_frames": n_frames,
        "n_alerts": n_alerts,
        "timeline": timeline,
        "false_alerts": false_alerts,
        "channel_valid": channel_valid,
        "channel_alert_count": channel_alert_count,
    }


def print_report(result: dict) -> None:
    print(f"Kadrlar: {result['n_frames']}  Alertlar: {result['n_alerts']}")
    print()
    print("-- Alert vaqt chizig'i (t, tomon, sabab) --")
    if not result["timeline"]:
        print("(alert yo'q)")
    for t, side, reason in result["timeline"]:
        print(f"  t={t:>8s}s  {side:<5s} {reason}")
    print()
    print("-- Yolg'on-alert taxmini (asl logda 'Normal' bo'lgan kadrda alert) --")
    if not result["false_alerts"]:
        print("(topilmadi)")
    for t, reason in result["false_alerts"]:
        print(f"  t={t:>8s}s  {reason}")
    print()
    print("-- Kanal statistikasi --")
    for ch, n in result["channel_valid"].items():
        pct = (100.0 * n / result["n_frames"]) if result["n_frames"] else 0.0
        print(f"  {ch:<10s} valid: {n}/{result['n_frames']} ({pct:.0f}%)")
    print("  trigger sabab bo'yicha alertlar:")
    if not result["channel_alert_count"]:
        print("    (yo'q)")
    for ch, n in sorted(result["channel_alert_count"].items(), key=lambda kv: -kv[1]):
        print(f"    {ch}: {n}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.replay",
                                      description="Log CSV -> Metrics -> Monitor replay (kamerasiz).")
    parser.add_argument("log", type=str, help="CSV log fayli (tgf --log bilan yozilgan).")
    parser.add_argument("--set", action="append", default=[], metavar="key=val",
                         help="Config maydonini bekor qilish (bir nechta marta ishlatsa bo'ladi).")
    parser.add_argument("--sensitivity", choices=["low", "medium", "high"], default=None)
    parser.add_argument("--baseline", type=str, default=None,
                         help="Baseline JSON fayl (aks holda logdagi dastlabki 'Normal' kadrlardan avto-kalibratsiya).")
    parser.add_argument("--calib-rows", type=int, default=30,
                         help="Avto-baseline uchun ishlatiladigan dastlabki 'Normal' kadrlar soni (standart 30).")
    args = parser.parse_args(argv)

    path = Path(args.log)
    if not path.exists():
        print(f"Fayl topilmadi: {path}", file=sys.stderr)
        return 1

    rows = load_rows(path)
    if not rows:
        print("CSV bo'sh yoki o'qib bo'lmadi.", file=sys.stderr)
        return 1

    cfg = Config()
    if args.sensitivity:
        cfg.sensitivity = args.sensitivity
    cfg = apply_overrides(cfg, args.set)

    if args.baseline:
        from tgf.calibration import load_baseline
        baseline = load_baseline(args.baseline)
        if baseline is None:
            print(f"Baseline o'qib bo'lmadi: {args.baseline}", file=sys.stderr)
            return 1
    else:
        baseline = build_baseline(rows, args.calib_rows)

    result = replay(rows, cfg, baseline)
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
