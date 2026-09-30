"""CLI entry point: python -m tgf [--headless] [--calibrate] [--config P] [--fps N] [--camera I]."""
from __future__ import annotations

import argparse
import csv
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from . import __version__
from .alerts import Alerter
from .calibration import Baseline, load_baseline as _calib_load_baseline, save_baseline as _calib_save_baseline
from .config import Config
from .paths import baseline_path_for, channel, default_config_path
from .pipeline import CalibState, Pipeline, ReanchorReason
from .profiles import load_bank as _load_bank, profiles_path_for
from .sounds import list_system_sounds

_NOPOSE_FPS = 1.0
_RETRY_MIN, _RETRY_MAX = 5.0, 60.0
_MAX_READ_FAILS = 25
_DISPLAY_HZ = 30.0
_STATS_INTERVAL = 5.0


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tgf", description="Ultra-yengil webcam postura monitor.")
    p.add_argument("--version", action="version", version=f"tgf {__version__} ({channel()})")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--config", type=str, default=str(default_config_path()))
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--camera", type=int, default=None)
    p.add_argument("--sound", type=str, default=None)
    p.add_argument("--volume", type=float, default=None)
    p.add_argument("--list-sounds", action="store_true")
    p.add_argument("--test-sound", action="store_true")
    p.add_argument("--log", type=str, default=None, help="CSV log path.")
    p.add_argument("--stats", action="store_true", help="Print p50/p95 every 5 s to stderr.")
    p.add_argument("--sensitivity", choices=["low", "medium", "high"], default=None,
                   help="Alert sensitivity preset (low/medium/high).")
    p.add_argument("--no-auto", action="store_true", help="Auto re-anchorni o'chirish.")
    p.add_argument("--profiles", action="store_true", help="Saqlangan profillar ro'yxatini chiqarish.")
    p.add_argument("--reset-profiles", action="store_true", help="Barcha profillarni o'chirish.")
    p.add_argument("--model", type=int, choices=[0, 1, 2], default=None,
                   help="MediaPipe model_complexity (0=fast, 1=balanced, 2=accurate).")
    return p.parse_args(argv)


def _load_baseline(path: Path) -> Optional[Baseline]:
    return _calib_load_baseline(path)


def _save_baseline(baseline: Baseline, path: Path) -> None:
    _calib_save_baseline(baseline, path)


# --- Stats tracking ---
class _PerfStats:
    def __init__(self) -> None:
        self._infer: list[float] = []
        self._cap_age: list[float] = []

    def record(self, infer_ms: float, cap_age_ms: float) -> None:
        self._infer.append(infer_ms)
        self._cap_age.append(cap_age_ms)

    def report(self) -> str:
        def _pct(lst: list[float], p: int) -> float:
            if not lst:
                return 0.0
            s = sorted(lst)
            idx = max(0, int(len(s) * p / 100) - 1)
            return s[idx]
        r = (f"infer_ms p50={_pct(self._infer,50):.1f} p95={_pct(self._infer,95):.1f} | "
             f"cap_age_ms p50={_pct(self._cap_age,50):.1f} p95={_pct(self._cap_age,95):.1f}")
        self._infer.clear()
        self._cap_age.clear()
        return r


class _Runner:
    def __init__(self, cfg: Config, headless: bool, force_calibrate: bool,
                 baseline_path: Path, cfg_path: Path,
                 log_path: Optional[str], stats: bool) -> None:
        self.cfg = cfg
        self.headless = headless
        self.force_calibrate = force_calibrate
        self.baseline_path = baseline_path
        self.cfg_path = cfg_path
        self.log_path = log_path
        self.do_stats = stats
        self.cam = None
        self.pose = None
        self.pipeline: Optional[Pipeline] = None
        self.alerter = Alerter(cfg)
        self._running = True
        self._perf = _PerfStats()
        self._next_stats = 0.0
        # For threaded mode: shared state between worker and display thread
        self._lock = threading.Lock()
        self._latest_result = None
        self._latest_frame = None
        # CSV logging
        self._log_file = None
        self._log_writer = None
        self._log_buf: list[list] = []
        self._log_flush_t = 0.0

    def _on_signal(self, signum, frame) -> None:
        if hasattr(signal, "SIGUSR1") and signum == signal.SIGUSR1:
            if self.pipeline:
                self.pipeline.request_recalibrate()
        else:
            self._running = False

    def _install_signals(self) -> None:
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, self._on_signal)

    def _sleep(self, sec: float) -> None:
        end = time.monotonic() + sec
        while self._running and time.monotonic() < end:
            time.sleep(min(0.25, max(0.0, end - time.monotonic())))

    def _open_camera(self) -> bool:
        from .camera import Camera, CameraError
        delay = _RETRY_MIN
        while self._running:
            try:
                self.cam = Camera(self.cfg)
                return True
            except CameraError as e:
                print(e, file=sys.stderr, flush=True)
                if not self.headless:
                    return False
                self._sleep(delay)
                delay = min(delay * 2, _RETRY_MAX)
        return False

    def _reopen_camera(self) -> bool:
        if self.cam is not None:
            self.cam.close()
            self.cam = None
        return self._open_camera()

    def _cycle_sound(self) -> None:
        names = list_system_sounds()
        if not names:
            return
        try:
            idx = names.index(self.cfg.sound)
        except ValueError:
            idx = -1
        self.cfg.sound = names[(idx + 1) % len(names)]
        self.alerter.preview(self.cfg.sound)
        try:
            self.cfg.save(self.cfg_path)
        except OSError:
            pass

    def _print_profiles(self) -> None:
        if not self.pipeline:
            return
        rows = self.pipeline.profiles_snapshot()
        if not rows:
            print("Profillar yo'q.", file=sys.stderr)
            return
        for i, ctx, last_used in rows:
            yaw = f"{ctx.body_yaw_deg:.0f}°" if ctx.body_yaw_deg is not None else "?"
            print(f"[{i}] cx={ctx.cx:.2f} scale={ctx.scale:.2f} yaw={yaw} "
                  f"last_used={time.strftime('%H:%M:%S', time.localtime(last_used))}",
                  file=sys.stderr)

    def _open_log(self) -> None:
        if not self.log_path:
            return
        try:
            p = Path(self.log_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(p, "w", newline="", encoding="utf-8")
            self._log_writer = csv.writer(self._log_file)
            self._log_writer.writerow([
                "t", "seq", "cap_age_ms", "infer_ms", "loop_ms", "status",
                "shoulder", "head", "lean",
                "ls_x", "ls_y", "ls_vis", "rs_x", "rs_y", "rs_vis",
                "le_x", "le_y", "le_vis", "re_x", "re_y", "re_vis",
                "d_shoulder", "d_head", "d_lean",
                "body_yaw_deg", "head_yaw_proxy", "cx", "scale", "edge",
            ])
        except OSError as e:
            print(f"Log açılamadı: {e}", file=sys.stderr)

    def _write_log(self, row: list) -> None:
        if not self._log_writer:
            return
        self._log_buf.append(row)
        now = time.monotonic()
        if now - self._log_flush_t >= 2.0:
            try:
                for r in self._log_buf:
                    self._log_writer.writerow(r)
                self._log_file.flush()
                self._log_buf.clear()
                self._log_flush_t = now
            except OSError:
                pass

    def _close_log(self) -> None:
        if self._log_writer and self._log_buf:
            try:
                for r in self._log_buf:
                    self._log_writer.writerow(r)
            except OSError:
                pass
        if self._log_file:
            try:
                self._log_file.close()
            except OSError:
                pass

    # --- inference worker (runs in background thread for debug mode) ---
    def _inference_loop(self) -> None:
        seq = 0
        last_frame_seq = 0
        while self._running:
            frame_obj = None
            if hasattr(self.cam, '_grabber'):
                frame_obj = self.cam._grabber.get_new(last_frame_seq)
            if frame_obj is None:
                time.sleep(0.005)
                continue
            last_frame_seq = frame_obj.seq
            frame = frame_obj.data
            cap_ts = frame_obj.ts
            seq += 1

            import cv2
            h, w = frame.shape[:2]
            if w > self.cfg.width:
                frame = cv2.resize(frame, (self.cfg.width, max(1, round(h * self.cfg.width / w))))

            aspect = frame.shape[1] / frame.shape[0]
            t0 = time.monotonic()
            result = self.pipeline.process(frame, cap_ts, aspect, self.pose)
            t_end = time.monotonic()

            loop_ms = (t_end - t0) * 1000
            infer_ms = result.timings.get("infer_ms", loop_ms)
            cap_age_ms = (t0 - cap_ts) * 1000

            self._perf.record(infer_ms, cap_age_ms)

            now = time.monotonic()
            if result.calib_state == CalibState.RUNNING:
                state = result.state
                status, alert = state.status, state.alert
                if alert:
                    side = "left" if status == "Tilt Left" else "right" if status == "Tilt Right" else None
                    self.alerter.fire(side)
                self.alerter.tick(now)

                # power save headless NoPose
                if self.headless and status == "NoPose":
                    self.cam.set_fps(_NOPOSE_FPS)
                else:
                    self.cam.set_fps(self.cfg.capture_fps)

                # log
                if self._log_writer and result.lm is not None:
                    lm = result.lm
                    m = result.metrics
                    ctx = result.ctx
                    d = state.deltas or {}
                    def _f(v): return f"{v:.4f}" if v is not None else ""
                    row = [
                        f"{cap_ts:.3f}", seq, f"{cap_age_ms:.1f}", f"{infer_ms:.1f}", f"{loop_ms:.1f}", status,
                        _f(m.shoulder if m else None), _f(m.head if m else None), _f(m.lean if m else None),
                        _f(lm.left_shoulder.x), _f(lm.left_shoulder.y), _f(lm.left_shoulder.visibility),
                        _f(lm.right_shoulder.x), _f(lm.right_shoulder.y), _f(lm.right_shoulder.visibility),
                        _f(lm.left_ear.x), _f(lm.left_ear.y), _f(lm.left_ear.visibility),
                        _f(lm.right_ear.x), _f(lm.right_ear.y), _f(lm.right_ear.visibility),
                        _f(d.get("shoulder")), _f(d.get("head")), _f(d.get("lean")),
                        _f(ctx.body_yaw_deg if ctx else None), _f(ctx.head_yaw_proxy if ctx else None),
                        _f(ctx.cx if ctx else None), _f(ctx.scale if ctx else None),
                        (str(int(ctx.edge)) if ctx else ""),
                    ]
                    self._write_log(row)

            if self.do_stats and now >= self._next_stats:
                print(self._perf.report(), file=sys.stderr, flush=True)
                self._next_stats = now + _STATS_INTERVAL

            with self._lock:
                self._latest_result = result
                self._latest_frame = frame

    def run(self) -> int:
        from .pose import PoseEstimator

        self._install_signals()
        if not self._open_camera():
            return 0 if not self._running else 2

        self.pose = PoseEstimator(self.cfg)
        existing = None if self.force_calibrate else _load_baseline(self.baseline_path)
        profiles_path = profiles_path_for(self.baseline_path)
        bank = _load_bank(
            profiles_path,
            max_profiles=self.cfg.max_profiles,
            ctx_dx=self.cfg.ctx_dx,
            ctx_scale=self.cfg.ctx_scale,
            ctx_yaw=self.cfg.ctx_yaw,
        )
        if not bank.profiles and existing is not None:
            # Migration: the pre-Stage-11 calibration.json becomes the first
            # profile; its context is unknown until the next stable frame.
            from .profiles import ProfileContext
            bank.upsert(ProfileContext(cx=0.5, scale=0.3, body_yaw_deg=None), existing)
        self.pipeline = Pipeline(self.cfg, self.baseline_path, existing,
                                  profile_bank=bank, profiles_path=profiles_path)
        self._open_log()
        self._next_stats = time.monotonic() + _STATS_INTERVAL

        cv2 = None
        if not self.headless:
            import cv2 as _cv2
            cv2 = _cv2

        try:
            if not self.headless:
                # Debug: inference in worker thread, display at ~30 Hz in main thread
                worker = threading.Thread(target=self._inference_loop, daemon=True)
                worker.start()

                display_interval = 1.0 / _DISPLAY_HZ
                while self._running:
                    with self._lock:
                        result = self._latest_result
                        frame = self._latest_frame

                    if frame is not None and result is not None:
                        from .overlay import draw
                        cs = result.calib_state
                        if cs == CalibState.CALIBRATING:
                            prefix = (
                                "Yangi joylashuv: to'g'ri o'tiring "
                                if result.reanchor == ReanchorReason.NEW
                                else "Kalibratsiya "
                            )
                            extra = f"{prefix}{result.calib_progress*100:.0f}% | {self.cfg.sound}"
                        elif cs in (CalibState.IDLE, CalibState.WAITING_PERSON):
                            extra = f"Kutilmoqda... | {self.cfg.sound}"
                        else:
                            extra = self.cfg.sound
                        status = result.state.status if cs == CalibState.RUNNING else "NoPose"
                        label = "Burilgan/Chetda" if status == "Turned" else status
                        cv2.imshow("TGF", draw(frame, result.lm, result.metrics, status, extra=extra,
                                                ctx=result.ctx, label=label))

                    key = cv2.waitKey(int(display_interval * 1000)) & 0xFF
                    if key == ord("q"):
                        break
                    if key == ord("c"):
                        if self.pipeline:
                            self.pipeline.request_recalibrate()
                    if key == ord("s"):
                        self._cycle_sound()
                    if key == ord("p"):
                        self._print_profiles()

                self._running = False
                worker.join(timeout=3.0)
            else:
                # Headless: single thread
                fails = 0
                while self._running:
                    frame = self.cam.read()
                    if frame is None:
                        fails += 1
                        time.sleep(0.2)
                        if fails >= _MAX_READ_FAILS:
                            fails = 0
                            if not self._reopen_camera():
                                break
                        continue
                    fails = 0
                    aspect = frame.shape[1] / frame.shape[0]
                    cap_ts = time.monotonic()
                    result = self.pipeline.process(frame, cap_ts, aspect, self.pose)
                    now = time.monotonic()

                    if result.calib_state == CalibState.RUNNING:
                        state = result.state
                        status, alert = state.status, state.alert
                        if alert:
                            side = "left" if status == "Tilt Left" else "right" if status == "Tilt Right" else None
                            self.alerter.fire(side)
                        self.alerter.tick(now)
                        if status == "NoPose":
                            self.cam.set_fps(_NOPOSE_FPS)
                        else:
                            self.cam.set_fps(self.cfg.capture_fps)
                    if self.do_stats and now >= self._next_stats:
                        print(self._perf.report(), file=sys.stderr, flush=True)
                        self._next_stats = now + _STATS_INTERVAL
        finally:
            self._running = False
            if self.cam is not None:
                self.cam.close()
            if self.pose is not None:
                self.pose.close()
            if cv2 is not None:
                cv2.destroyAllWindows()
            self._close_log()
        return 0


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)

    if args.list_sounds:
        for name in list_system_sounds():
            print(name)
        return 0

    cfg_path = Path(args.config).expanduser()
    cfg = Config.load(cfg_path)
    if not cfg_path.exists():
        try:
            cfg.save(cfg_path)
        except OSError:
            pass
    if args.fps is not None:
        cfg.fps = args.fps
    if args.camera is not None:
        cfg.camera_index = args.camera
    if args.sound is not None:
        cfg.sound = args.sound
    if args.volume is not None:
        cfg.volume = args.volume
    if args.sensitivity is not None:
        cfg.sensitivity = args.sensitivity
    if args.model is not None:
        cfg.model_complexity = args.model
    if args.no_auto:
        cfg.auto_reanchor = False
    cfg.sanitize()

    if args.test_sound:
        Alerter(cfg).preview(cfg.sound)
        time.sleep(2.0)
        return 0

    bpath = baseline_path_for(cfg_path)
    ppath = profiles_path_for(bpath)

    if args.reset_profiles:
        try:
            ppath.unlink()
        except OSError:
            pass
        print("Profillar tozalandi.", file=sys.stderr)
        return 0

    if args.profiles:
        bank = _load_bank(ppath, max_profiles=cfg.max_profiles,
                           ctx_dx=cfg.ctx_dx, ctx_scale=cfg.ctx_scale, ctx_yaw=cfg.ctx_yaw)
        if not bank.profiles:
            print("Profillar yo'q.", file=sys.stderr)
        for i, p in enumerate(bank.profiles):
            yaw = f"{p.ctx.body_yaw_deg:.0f}°" if p.ctx.body_yaw_deg is not None else "?"
            print(f"[{i}] cx={p.ctx.cx:.2f} scale={p.ctx.scale:.2f} yaw={yaw}", file=sys.stderr)
        return 0

    runner = _Runner(
        cfg, args.headless, args.calibrate,
        baseline_path_for(cfg_path), cfg_path,
        args.log, args.stats,
    )
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
