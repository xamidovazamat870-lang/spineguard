"""Posture state machine: per-channel deltas, fused score, hysteresis, hold-based alert."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .calibration import Baseline
from .config import Config
from .filters import MovingAverage, OneEuroFilter
from .geometry import Metrics, PoseContext

VALID_STATUSES = {"Normal", "Tilt Left", "Tilt Right", "NoPose", "Turned"}

Filter = Union[MovingAverage, OneEuroFilter]

# Fusion weights (renormalized over valid channels)
_W = {"shoulder": 0.5, "head": 0.3, "neck": 0.2}

_SENSITIVITY = {"low": 1.3, "medium": 1.0, "high": 0.75}


@dataclass
class State:
    status: str
    deltas: Optional[dict]
    alert: bool
    reason: str = ""  # which channel(s) triggered


def _make_filter(cfg: Config) -> Filter:
    if cfg.filter == "ma":
        return MovingAverage(cfg.window)
    return OneEuroFilter(cfg.oe_min_cutoff, cfg.oe_beta)


class PostureMonitor:
    def __init__(self, cfg: Config, baseline: Baseline) -> None:
        self.cfg = cfg
        self.baseline = baseline
        self._sh_f: Filter = _make_filter(cfg)
        self._hd_f: Filter = _make_filter(cfg)
        self._nk_f: Filter = _make_filter(cfg)
        self._lean_f: Filter = _make_filter(cfg)
        self._tilted = False
        self._side: Optional[str] = None
        self._since: Optional[float] = None
        self._none_since: Optional[float] = None
        self._last: Optional[State] = None

    # ── thresholds ──────────────────────────────────────────────────────────
    def _thr(self, cfg_val: float, sigma: float, left: bool) -> float:
        k = 3.0
        base = max(cfg_val, k * sigma)
        sens = _SENSITIVITY.get(getattr(self.cfg, "sensitivity", "medium"), 1.0)
        factor = (self.cfg.left_factor if left else self.cfg.right_factor) * sens
        return base * factor

    def _thresholds(self) -> dict:
        bl = self.baseline
        sh_l = self._thr(self.cfg.shoulder_deg, bl.sigma_shoulder, left=True)
        sh_r = self._thr(self.cfg.shoulder_deg, bl.sigma_shoulder, left=False)
        hd_l = self._thr(self.cfg.head_deg, bl.sigma_head, left=True)
        hd_r = self._thr(self.cfg.head_deg, bl.sigma_head, left=False)
        nk_l = self._thr(self.cfg.neck_deg, bl.sigma_neck, left=True)
        nk_r = self._thr(self.cfg.neck_deg, bl.sigma_neck, left=False)
        return {"sh_l": sh_l, "sh_r": sh_r, "hd_l": hd_l, "hd_r": hd_r, "nk_l": nk_l, "nk_r": nk_r}

    # ── update ───────────────────────────────────────────────────────────────
    def _reset_timer(self) -> None:
        self._tilted = False
        self._side = None
        self._since = None

    def _reset_filters(self) -> None:
        for f in (self._sh_f, self._hd_f, self._nk_f, self._lean_f):
            f.reset()

    def update(self, m: Optional[Metrics], now: float, ctx: Optional[PoseContext] = None) -> State:
        if m is None:
            if self._none_since is None:
                self._none_since = now
            if (
                now - self._none_since < self.cfg.nopose_grace_sec
                and self._last is not None
                and self._last.status != "NoPose"
            ):
                return State(status=self._last.status, deltas=self._last.deltas, alert=False,
                             reason=self._last.reason)
            self._reset_timer()
            self._reset_filters()
            self._last = State(status="NoPose", deltas=None, alert=False)
            return self._last
        self._none_since = None

        bl = self.baseline

        # --- gating: yaw/edge invalidate or de-weight channels (Stage 10) ---
        head_gated_out = False
        yaw_scale = 1.0
        if ctx is not None:
            if abs(ctx.head_yaw_proxy) > self.cfg.head_yaw_max:
                head_gated_out = True
            body_yaw = ctx.body_yaw_deg
            if body_yaw is not None:
                if abs(body_yaw) > self.cfg.body_yaw_invalid:
                    yaw_scale = 0.0
                elif abs(body_yaw) > self.cfg.body_yaw_max:
                    yaw_scale = 0.5

        edge_scale = 0.5 if (ctx is not None and ctx.edge) else 1.0

        m_head = None if head_gated_out else m.head

        # Filter per channel, but only update filter if channel is valid
        d_sh = self._sh_f.update(m.shoulder - bl.shoulder, now) if m.shoulder is not None else None
        d_hd = self._hd_f.update(m_head - bl.head, now) if m_head is not None else None
        d_nk = self._nk_f.update(m.neck - bl.neck, now) if m.neck is not None else None
        d_ln = self._lean_f.update(m.lean - bl.lean, now) if m.lean is not None else None

        deltas = {"shoulder": d_sh, "head": d_hd, "neck": d_nk, "lean": d_ln}
        thr = self._thresholds()

        # Fused score S = Σ w_i * d_i/thr_i (renormalized over valid channels)
        # shoulder/neck weights scaled by body-yaw gate and edge proximity.
        chan_scale = {"shoulder": yaw_scale * edge_scale, "head": edge_scale, "neck": yaw_scale * edge_scale}
        channels = [
            ("shoulder", d_sh, thr["sh_l"], thr["sh_r"]),
            ("head",     d_hd, thr["hd_l"], thr["hd_r"]),
            ("neck",     d_nk, thr["nk_l"], thr["nk_r"]),
        ]
        valid_weight = 0.0
        S = 0.0
        voted: list[str] = []
        any_channel_usable = False
        for name, d, thr_l, thr_r in channels:
            if d is None:
                continue
            scale = chan_scale[name]
            if scale <= 0.0:
                continue
            any_channel_usable = True
            w = _W[name] * scale
            valid_weight += w
            thr_i = thr_l if d >= 0 else thr_r
            ratio = d / thr_i if thr_i > 0 else 0.0
            S += w * ratio
            if abs(ratio) >= 1.0:
                voted.append(name)
        if valid_weight > 0:
            S /= valid_weight

        if not any_channel_usable:
            # Person visible but every channel gated out by yaw/edge: don't fire
            # false alerts; freeze (don't reset) the hold-timer.
            self._last = State(status="Turned", deltas=deltas, alert=False, reason="turned")
            return self._last

        exit_ratio = getattr(self.cfg, "exit_ratio", 0.7)

        if self._tilted:
            exit_s = exit_ratio
            if self._side == "left" and S < exit_s:
                self._reset_timer()
            elif self._side == "right" and S > -exit_s:
                self._reset_timer()
        else:
            # Any single channel ≥ 1.2× OR fused |S| ≥ 1
            single_strong = any(
                d is not None and chan_scale[name] > 0.0
                and abs(d) / (thr_l if d >= 0 else thr_r) >= 1.2
                for name, d, thr_l, thr_r in channels
            )
            if abs(S) >= 1.0 or single_strong:
                self._tilted = True
                self._side = "left" if S >= 0 else "right"
                self._since = now

        if not self._tilted:
            self._last = State(status="Normal", deltas=deltas, alert=False)
            return self._last

        status = "Tilt Left" if self._side == "left" else "Tilt Right"
        held = (now - self._since) if self._since is not None else 0.0
        reason = "+".join(voted) if voted else ""
        self._last = State(status=status, deltas=deltas, alert=held >= self.cfg.hold_sec, reason=reason)
        return self._last
