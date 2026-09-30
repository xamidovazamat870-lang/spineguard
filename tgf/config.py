"""Config dataclass with validated JSON persistence."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Config:
    fps: int = 8
    width: int = 640
    height: int = 480
    window: int = 12
    enter_deg: float = 7.0
    exit_deg: float = 5.0
    left_threshold: float = 6.0
    right_threshold: float = 8.0
    hold_sec: float = 3.0
    cooldown_sec: float = 30.0
    calib_sec: float = 3.0
    visibility_min: float = 0.5
    camera_index: int = 0
    nopose_grace_sec: float = 1.5
    sound: str = "Tink"
    sound_left: str = ""
    sound_right: str = ""
    volume: float = 1.0
    repeat: int = 1
    repeat_gap_sec: float = 0.4
    filter: str = "oneeuro"
    oe_min_cutoff: float = 1.0
    oe_beta: float = 0.08
    capture_fps: int = 15
    mp_smooth: bool = False
    model_complexity: int = 0
    # Stage 9: per-channel thresholds and sensitivity
    shoulder_deg: float = 4.0
    head_deg: float = 6.0
    neck_deg: float = 5.0
    left_factor: float = 0.85
    right_factor: float = 1.0
    exit_ratio: float = 0.7
    sensitivity: str = "medium"
    visibility_min_shoulder: float = 0.35
    # Stage 10: yaw-invariant 3D angle + turn/edge gating
    use_world: bool = True
    head_yaw_max: float = 0.6
    body_yaw_max: float = 35.0
    body_yaw_invalid: float = 55.0
    edge_margin: float = 0.08
    # Stage 11: smart re-anchor (context profiles + safe auto-calibration)
    auto_reanchor: bool = True
    ctx_dx: float = 0.15
    ctx_scale: float = 0.20
    ctx_yaw: float = 20.0
    ctx_settle_sec: float = 4.0
    max_profiles: int = 6
    away_sec: float = 20.0
    reanchor_roll_guard: float = 15.0
    # Deprecated (kept for backward compat, ignored in logic)
    # enter_deg, exit_deg, left_threshold, right_threshold

    def sanitize(self) -> "Config":
        """Coerce types and clamp to safe ranges; bad values fall back to defaults."""
        for f in fields(self):
            default = f.default
            v = getattr(self, f.name)
            try:
                if isinstance(v, bool) and not isinstance(default, bool):
                    raise ValueError
                v = bool(v) if isinstance(default, bool) else type(default)(v)
                if v != v or v in (float("inf"), float("-inf")):
                    raise ValueError
            except (TypeError, ValueError):
                v = default
            setattr(self, f.name, v)
        self.fps = min(max(self.fps, 1), 30)
        self.width = max(self.width, 160)
        self.height = max(self.height, 120)
        self.window = max(self.window, 1)
        self.enter_deg = max(self.enter_deg, 0.1)
        self.exit_deg = min(max(self.exit_deg, 0.0), self.enter_deg)
        self.hold_sec = max(self.hold_sec, 0.0)
        self.cooldown_sec = max(self.cooldown_sec, 0.0)
        self.calib_sec = max(self.calib_sec, 1.0)
        self.visibility_min = min(max(self.visibility_min, 0.0), 1.0)
        self.camera_index = max(self.camera_index, 0)
        self.nopose_grace_sec = max(self.nopose_grace_sec, 0.0)
        self.volume = min(max(self.volume, 0.0), 2.0)
        self.repeat = min(max(self.repeat, 1), 5)
        self.repeat_gap_sec = min(max(self.repeat_gap_sec, 0.1), 5.0)
        if self.filter not in ("oneeuro", "ma"):
            self.filter = "oneeuro"
        self.oe_min_cutoff = max(self.oe_min_cutoff, 0.01)
        self.oe_beta = max(self.oe_beta, 0.0)
        self.capture_fps = min(max(self.capture_fps, 1), 60)
        self.model_complexity = min(max(self.model_complexity, 0), 2)
        self.shoulder_deg = max(self.shoulder_deg, 0.1)
        self.head_deg = max(self.head_deg, 0.1)
        self.neck_deg = max(self.neck_deg, 0.1)
        self.left_factor = max(self.left_factor, 0.1)
        self.right_factor = max(self.right_factor, 0.1)
        self.exit_ratio = min(max(self.exit_ratio, 0.0), 1.5)
        if self.sensitivity not in ("low", "medium", "high"):
            self.sensitivity = "medium"
        self.visibility_min_shoulder = min(max(self.visibility_min_shoulder, 0.0), 1.0)
        self.head_yaw_max = min(max(self.head_yaw_max, 0.05), 5.0)
        self.body_yaw_max = min(max(self.body_yaw_max, 1.0), 89.0)
        self.body_yaw_invalid = min(max(self.body_yaw_invalid, self.body_yaw_max), 90.0)
        self.edge_margin = min(max(self.edge_margin, 0.0), 0.4)
        self.ctx_dx = min(max(self.ctx_dx, 0.01), 1.0)
        self.ctx_scale = min(max(self.ctx_scale, 0.01), 1.0)
        self.ctx_yaw = min(max(self.ctx_yaw, 1.0), 90.0)
        self.ctx_settle_sec = min(max(self.ctx_settle_sec, 0.5), 30.0)
        self.max_profiles = min(max(self.max_profiles, 1), 20)
        self.away_sec = min(max(self.away_sec, 1.0), 300.0)
        self.reanchor_roll_guard = min(max(self.reanchor_roll_guard, 1.0), 45.0)
        return self

    DEPRECATED_KEYS = ("enter_deg", "exit_deg", "left_threshold", "right_threshold")

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            return cls()
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        found_deprecated = [k for k in cls.DEPRECATED_KEYS if k in data]
        if found_deprecated:
            import sys
            print(
                "Ogohlantirish: config.json'da eskirgan kalitlar bor va "
                f"e'tiborga olinmaydi: {', '.join(found_deprecated)}. "
                "O'rniga shoulder_deg/head_deg/neck_deg/left_factor/right_factor "
                "ishlatiladi.",
                file=sys.stderr,
            )
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        try:
            return cls(**filtered).sanitize()
        except TypeError:
            return cls()

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(tmp, p)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
