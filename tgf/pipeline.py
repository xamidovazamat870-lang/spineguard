"""Pipeline: per-frame processing + non-blocking calibration state machine."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from .calibration import Baseline, CalibrationError, Calibrator, save_baseline as _calib_save_baseline
from .config import Config
from .geometry import Landmarks, Metrics, PoseContext, compute_metrics, compute_pose_context
from .monitor import PostureMonitor, State
from .profiles import (
    Profile,
    ProfileBank,
    ProfileContext,
    save_bank as _save_bank,
)


class CalibState(Enum):
    IDLE = auto()
    WAITING_PERSON = auto()
    CALIBRATING = auto()
    RUNNING = auto()


class ReanchorReason(Enum):
    """Why the RUNNING state is (re)calibrating a new context, for overlay/UI."""
    SWITCHED = auto()   # quietly matched a known profile
    NEW = auto()         # unrecognized context; running blocking-free calibration


@dataclass
class Result:
    lm: Optional[Landmarks]
    metrics: Optional[Metrics]
    state: State
    timings: dict
    calib_state: CalibState
    calib_progress: float  # 0..1 during CALIBRATING
    ctx: Optional[PoseContext] = None
    reanchor: Optional[ReanchorReason] = None  # set the frame a re-anchor event fires


def _save_baseline(baseline: Baseline, path: Path) -> None:
    _calib_save_baseline(baseline, path)


_DUMMY_STATE = State(status="NoPose", deltas=None, alert=False)


class Pipeline:
    """Stateful per-frame processor; call process() from any thread."""

    def __init__(
        self,
        cfg: Config,
        baseline_path: Path,
        existing_baseline: Optional[Baseline] = None,
        profile_bank: Optional[ProfileBank] = None,
        profiles_path: Optional[Path] = None,
    ) -> None:
        self.cfg = cfg
        self.baseline_path = baseline_path
        self.profiles_path = profiles_path
        self._monitor: Optional[PostureMonitor] = None
        self._recalibrate_flag = False

        self.bank = profile_bank if profile_bank is not None else ProfileBank(
            max_profiles=cfg.max_profiles, ctx_dx=cfg.ctx_dx, ctx_scale=cfg.ctx_scale, ctx_yaw=cfg.ctx_yaw,
        )
        self._active_profile: Optional[Profile] = None

        if existing_baseline is not None:
            self._monitor = PostureMonitor(cfg, existing_baseline)
            self._calib_state = CalibState.RUNNING
        else:
            self._calib_state = CalibState.IDLE

        self._calibrator: Optional[Calibrator] = None
        self._calib_start: float = 0.0
        self._calib_needed = int(max(3, cfg.calib_sec * cfg.fps * 0.4))
        self._person_since: Optional[float] = None  # for WAITING_PERSON
        self._pending_reason: Optional[ReanchorReason] = None

        # Away/return + context-drift tracking (Stage 11)
        self._none_since_pipeline: Optional[float] = None
        self._drift_since: Optional[float] = None
        self._drift_ctx: Optional[ProfileContext] = None
        self._settle_prev_cx: Optional[float] = None

    def request_recalibrate(self) -> None:
        self._recalibrate_flag = True

    def profiles_snapshot(self) -> list:
        """List (index, ctx, last_used) for CLI '-p' / '--profiles'."""
        return [(i, p.ctx, p.last_used) for i, p in enumerate(self.bank.profiles)]

    def reset_profiles(self) -> None:
        self.bank = ProfileBank(max_profiles=self.cfg.max_profiles)
        self._active_profile = None
        if self.profiles_path is not None:
            _save_bank(self.bank, self.profiles_path)

    def _start_calibrating(self, now: float, reason: ReanchorReason = ReanchorReason.NEW) -> None:
        self._calib_state = CalibState.CALIBRATING
        self._calibrator = Calibrator(min_samples=self._calib_needed)
        self._calib_start = now
        self._person_since = None
        self._pending_reason = reason

    @staticmethod
    def _to_profile_ctx(ctx: Optional[PoseContext]) -> Optional[ProfileContext]:
        if ctx is None:
            return None
        return ProfileContext(cx=ctx.cx, scale=ctx.scale, body_yaw_deg=ctx.body_yaw_deg)

    def process(self, frame, ts: float, aspect: float, pose_estimator) -> Result:
        t0 = time.monotonic()
        if self._recalibrate_flag:
            self._recalibrate_flag = False
            self._calib_state = CalibState.IDLE
            self._calibrator = None
            self._monitor = None
            self._person_since = None

        if hasattr(pose_estimator, "process_full"):
            lm, lm3 = pose_estimator.process_full(frame)
        else:
            lm, lm3 = pose_estimator.process(frame), None
        t_infer = time.monotonic()
        metrics = compute_metrics(
            lm, self.cfg.visibility_min, self.cfg.visibility_min_shoulder, aspect, lm3
        ) if lm is not None else None
        ctx = compute_pose_context(lm, lm3, self.cfg.edge_margin) if lm is not None else None

        now = ts  # use capture timestamp for consistency

        # --- calibration state machine ---
        if self._calib_state == CalibState.RUNNING:
            pass  # normal operation below
        elif self._calib_state == CalibState.IDLE:
            if metrics is not None:
                self._person_since = now
                self._calib_state = CalibState.WAITING_PERSON
            return Result(lm=lm, metrics=metrics, state=_DUMMY_STATE, timings={}, ctx=ctx,
                          calib_state=self._calib_state, calib_progress=0.0)
        elif self._calib_state == CalibState.WAITING_PERSON:
            if metrics is None:
                self._person_since = None
                self._calib_state = CalibState.IDLE
                return Result(lm=lm, metrics=metrics, state=_DUMMY_STATE, timings={}, ctx=ctx,
                              calib_state=self._calib_state, calib_progress=0.0)
            assert self._person_since is not None
            if now - self._person_since >= 1.0:
                self._start_calibrating(now)
            return Result(lm=lm, metrics=metrics, state=_DUMMY_STATE, timings={}, ctx=ctx,
                          calib_state=self._calib_state, calib_progress=0.0)
        elif self._calib_state == CalibState.CALIBRATING:
            assert self._calibrator is not None
            if metrics is not None:
                self._calibrator.add(metrics)
            elapsed = now - self._calib_start
            progress = min(elapsed / self.cfg.calib_sec, 1.0)
            reason = self._pending_reason
            if elapsed >= self.cfg.calib_sec:
                try:
                    baseline = self._calibrator.result()
                    accepted = self._accept_new_baseline(baseline, ctx, reason)
                    if accepted:
                        self._monitor = PostureMonitor(self.cfg, baseline)
                        _save_baseline(baseline, self.baseline_path)
                        self._calib_state = CalibState.RUNNING
                    else:
                        # Rejected by safety guard: keep previous monitor (if any) running,
                        # or fall back to IDLE if there wasn't one yet.
                        self._calib_state = CalibState.RUNNING if self._monitor else CalibState.IDLE
                except CalibrationError:
                    self._calib_state = CalibState.RUNNING if self._monitor else CalibState.IDLE
                self._calibrator = None
                self._person_since = None
                self._pending_reason = None
                self._drift_since = None
                self._drift_ctx = None
            return Result(lm=lm, metrics=metrics, state=_DUMMY_STATE, timings={}, ctx=ctx,
                          calib_state=self._calib_state, calib_progress=progress, reanchor=reason)

        # RUNNING
        now_mono = time.monotonic()
        if metrics is None:
            if self._none_since_pipeline is None:
                self._none_since_pipeline = now
        else:
            self._none_since_pipeline = None
        reanchor_event = self._maybe_reanchor(ctx, now, now_mono)
        state = self._monitor.update(metrics, now_mono, ctx) if self._monitor else _DUMMY_STATE
        t_end = time.monotonic()
        timings = {"infer_ms": (t_infer - t0) * 1000, "total_ms": (t_end - t0) * 1000}
        return Result(lm=lm, metrics=metrics, state=state, timings=timings,
                      calib_state=self._calib_state, calib_progress=1.0, ctx=ctx,
                      reanchor=reanchor_event)

    # ── Stage 11: context-aware re-anchor ───────────────────────────────────
    def _accept_new_baseline(
        self, baseline: Baseline, ctx: Optional[PoseContext], reason: Optional[ReanchorReason]
    ) -> bool:
        """Safety guard (b): reject a freshly-calibrated baseline that looks
        like noisy/bad data relative to the nearest known profile."""
        pctx = self._to_profile_ctx(ctx)
        guard = self.cfg.reanchor_roll_guard
        if pctx is not None and self.bank.profiles:
            nearest = self.bank.match(pctx) or min(
                self.bank.profiles,
                key=lambda p: abs(p.ctx.cx - pctx.cx) + abs(p.ctx.scale - pctx.scale),
                default=None,
            )
            if nearest is not None:
                if abs(baseline.shoulder - nearest.baseline.shoulder) > guard:
                    return False
        if pctx is not None:
            profile = self.bank.upsert(pctx, baseline)
            self._active_profile = profile
            if self.profiles_path is not None:
                _save_bank(self.bank, self.profiles_path)
        return True

    def _maybe_reanchor(
        self, ctx: Optional[PoseContext], now: float, now_mono: float
    ) -> Optional[ReanchorReason]:
        """Detect a stable context change and either quietly switch to a known
        profile or kick off a fresh (non-blocking) calibration for a new one."""
        if not self.cfg.auto_reanchor or ctx is None or self._monitor is None:
            self._drift_since = None
            self._drift_ctx = None
            return None

        pctx = self._to_profile_ctx(ctx)
        assert pctx is not None

        active = self._active_profile
        if active is not None and self._ctx_matches(active.ctx, pctx, self.cfg):
            self.bank.touch(active, now)
            self._drift_since = None
            self._drift_ctx = None
            return None

        # Safety (a): don't auto-learn while mid-alert/tilted; wait for Normal.
        last_state = self._monitor._last  # internal but same-package, read-only
        if last_state is not None and last_state.status not in ("Normal", "NoPose", None):
            self._drift_since = None
            self._drift_ctx = None
            return None

        # Require the context itself to be settled (low velocity) for ctx_settle_sec.
        if self._drift_since is None or self._settle_prev_cx is None or not self._ctx_matches(
            self._drift_ctx, pctx, self.cfg, loose=True
        ):
            self._drift_since = now
            self._drift_ctx = pctx
            self._settle_prev_cx = pctx.cx
            return None
        self._settle_prev_cx = pctx.cx

        if now - self._drift_since < self.cfg.ctx_settle_sec:
            return None

        # Context has moved and settled: either switch to a known profile
        # quietly, or start a fresh calibration for a brand-new one.
        match = self.bank.match(pctx)
        self._drift_since = None
        self._drift_ctx = None
        if match is not None:
            self._monitor = PostureMonitor(self.cfg, match.baseline)
            self._active_profile = match
            self.bank.touch(match, now)
            if self.profiles_path is not None:
                _save_bank(self.bank, self.profiles_path)
            return ReanchorReason.SWITCHED
        self._start_calibrating(now_mono, reason=ReanchorReason.NEW)
        return None  # the NEW event is reported once calibration completes

    @staticmethod
    def _ctx_matches(
        a: Optional[ProfileContext], b: Optional[ProfileContext], cfg: Config, loose: bool = False
    ) -> bool:
        """loose=True widens tolerance for 'did the drift itself settle' checks
        (distinct from the tighter 'is this the same known profile' matching
        used by ProfileBank.match, which has its own fixed tolerances)."""
        if a is None or b is None:
            return False
        mult = 1.5 if loose else 1.0
        if abs(a.cx - b.cx) > cfg.ctx_dx * mult:
            return False
        denom = max(a.scale, b.scale, 1e-6)
        if abs(a.scale - b.scale) / denom > cfg.ctx_scale * mult:
            return False
        if a.body_yaw_deg is not None and b.body_yaw_deg is not None:
            if abs(a.body_yaw_deg - b.body_yaw_deg) > cfg.ctx_yaw * mult:
                return False
        return True

    @property
    def calib_state(self) -> CalibState:
        return self._calib_state
