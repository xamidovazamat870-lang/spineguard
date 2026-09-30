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

    @property
    def calib_state(self) -> CalibState:
        return self._calib_state

    def request_recalibrate(self) -> None:
        self._recalibrate_flag = True

    def profiles_snapshot(self) -> list:
        """List (index, ctx, last_used) for CLI '-p' / '--profiles'."""
        return [(i, p.ctx, p.last_used) for i, p in enumerate(self.bank.profiles)]

    def _to_profile_ctx(self, ctx: PoseContext) -> ProfileContext:
        return ProfileContext(cx=ctx.cx, scale=ctx.scale, body_yaw_deg=ctx.body_yaw_deg)

    def _persist(self, baseline: Baseline) -> None:
        try:
            _save_baseline(baseline, self.baseline_path)
        except OSError:
            pass
        if self.profiles_path is not None:
            try:
                _save_bank(self.bank, self.profiles_path)
            except OSError:
                pass

    def _accept_new_baseline(
        self,
        new_bl: Baseline,
        ctx: PoseContext,
        reason: ReanchorReason,
    ) -> bool:
        # Guard: if we already have profiles, reject if roll deviates too far
        if self.bank.profiles:
            # Check against the nearest known profile's shoulder
            nearest = self.bank.match(self._to_profile_ctx(ctx))
            if nearest is None:
                # Fallback to the first profile if no direct match
                nearest = self.bank.profiles[0]
            if abs(new_bl.shoulder - nearest.baseline.shoulder) > self.cfg.reanchor_roll_guard:
                return False

        pctx = self._to_profile_ctx(ctx)
        self._active_profile = self.bank.upsert(pctx, new_bl)
        self._monitor = PostureMonitor(self.cfg, new_bl)
        self._persist(new_bl)
        return True

    def _maybe_reanchor(self, ctx: PoseContext, cap_ts: float, now: float) -> Optional[ReanchorReason]:
        if not self.cfg.auto_reanchor:
            return None

        pctx = self._to_profile_ctx(ctx)

        # 1. Match against known profile
        matched = self.bank.match(pctx)
        if matched is not None and matched is not self._active_profile:
            self._active_profile = matched
            self.bank.touch(matched, now)
            self._monitor = Post