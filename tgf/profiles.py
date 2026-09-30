"""Context-keyed baseline profiles: recognize a previously-seen location/pose."""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from .calibration import Baseline

MAX_PROFILES = 6

# Context-distance tolerances (Stage 11 defaults).
CTX_DX = 0.15
CTX_SCALE = 0.20  # relative
CTX_YAW = 20.0    # degrees


@dataclass
class ProfileContext:
    cx: float
    scale: float
    body_yaw_deg: Optional[float] = None


@dataclass
class Profile:
    ctx: ProfileContext
    baseline: Baseline
    last_used: float = field(default_factory=time.time)


def _matches(a: ProfileContext, b: ProfileContext, ctx_dx: float, ctx_scale: float, ctx_yaw: float) -> bool:
    if abs(a.cx - b.cx) > ctx_dx:
        return False
    denom = max(a.scale, b.scale, 1e-6)
    if abs(a.scale - b.scale) / denom > ctx_scale:
        return False
    if a.body_yaw_deg is not None and b.body_yaw_deg is not None:
        if abs(a.body_yaw_deg - b.body_yaw_deg) > ctx_yaw:
            return False
    return True


def _score(a: ProfileContext, b: ProfileContext, ctx_dx: float, ctx_scale: float, ctx_yaw: float) -> float:
    """Lower is closer; used to rank multiple matches."""
    denom = max(a.scale, b.scale, 1e-6)
    s = (abs(a.cx - b.cx) / ctx_dx) + (abs(a.scale - b.scale) / denom / ctx_scale)
    if a.body_yaw_deg is not None and b.body_yaw_deg is not None:
        s += abs(a.body_yaw_deg - b.body_yaw_deg) / ctx_yaw
    return s


class ProfileBank:
    """Small on-disk LRU set of (context -> baseline) profiles."""

    def __init__(
        self,
        max_profiles: int = MAX_PROFILES,
        ctx_dx: float = CTX_DX,
        ctx_scale: float = CTX_SCALE,
        ctx_yaw: float = CTX_YAW,
    ) -> None:
        self.max_profiles = max(1, max_profiles)
        self.ctx_dx = ctx_dx
        self.ctx_scale = ctx_scale
        self.ctx_yaw = ctx_yaw
        self.profiles: List[Profile] = []

    # ── matching ────────────────────────────────────────────────────────────
    def match(self, ctx: ProfileContext) -> Optional[Profile]:
        best: Optional[Profile] = None
        best_score = float("inf")
        for p in self.profiles:
            if _matches(p.ctx, ctx, self.ctx_dx, self.ctx_scale, self.ctx_yaw):
                s = _score(p.ctx, ctx, self.ctx_dx, self.ctx_scale, self.ctx_yaw)
                if s < best_score:
                    best_score = s
                    best = p
        return best

    # ── mutation ────────────────────────────────────────────────────────────
    def upsert(self, ctx: ProfileContext, baseline: Baseline, now: Optional[float] = None) -> Profile:
        now = time.time() if now is None else now
        existing = self.match(ctx)
        if existing is not None:
            existing.ctx = ctx
            existing.baseline = baseline
            existing.last_used = now
            return existing
        prof = Profile(ctx=ctx, baseline=baseline, last_used=now)
        self.profiles.append(prof)
        self._evict_lru()
        return prof

    def touch(self, profile: Profile, now: Optional[float] = None) -> None:
        profile.last_used = time.time() if now is None else now

    def _evict_lru(self) -> None:
        while len(self.profiles) > self.max_profiles:
            oldest = min(self.profiles, key=lambda p: p.last_used)
            self.profiles.remove(oldest)

    # ── persistence ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "profiles": [
                {
                    "ctx": asdict(p.ctx),
                    "baseline": asdict(p.baseline),
                    "last_used": p.last_used,
                }
                for p in self.profiles
            ]
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        max_profiles: int = MAX_PROFILES,
        ctx_dx: float = CTX_DX,
        ctx_scale: float = CTX_SCALE,
        ctx_yaw: float = CTX_YAW,
    ) -> "ProfileBank":
        bank = cls(max_profiles=max_profiles, ctx_dx=ctx_dx, ctx_scale=ctx_scale, ctx_yaw=ctx_yaw)
        raw = data.get("profiles") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return bank
        for item in raw:
            try:
                ctx = ProfileContext(
                    cx=float(item["ctx"]["cx"]),
                    scale=float(item["ctx"]["scale"]),
                    body_yaw_deg=(
                        None if item["ctx"].get("body_yaw_deg") is None
                        else float(item["ctx"]["body_yaw_deg"])
                    ),
                )
                bl_data = item["baseline"]
                baseline = Baseline(
                    shoulder=float(bl_data["shoulder"]),
                    head=float(bl_data["head"]),
                    lean=float(bl_data["lean"]),
                    neck=float(bl_data.get("neck", 0.0)),
                    sigma_shoulder=float(bl_data.get("sigma_shoulder", 1.0)),
                    sigma_head=float(bl_data.get("sigma_head", 1.0)),
                    sigma_neck=float(bl_data.get("sigma_neck", 1.0)),
                )
                last_used = float(item.get("last_used", time.time()))
            except (KeyError, TypeError, ValueError):
                continue
            bank.profiles.append(Profile(ctx=ctx, baseline=baseline, last_used=last_used))
        bank._evict_lru()
        return bank


def load_bank(
    path: str | Path,
    max_profiles: int = MAX_PROFILES,
    ctx_dx: float = CTX_DX,
    ctx_scale: float = CTX_SCALE,
    ctx_yaw: float = CTX_YAW,
) -> ProfileBank:
    empty = lambda: ProfileBank(max_profiles=max_profiles, ctx_dx=ctx_dx, ctx_scale=ctx_scale, ctx_yaw=ctx_yaw)
    p = Path(path)
    if not p.exists():
        return empty()
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return empty()
    if not isinstance(data, dict):
        return empty()
    return ProfileBank.from_dict(data, max_profiles=max_profiles, ctx_dx=ctx_dx, ctx_scale=ctx_scale, ctx_yaw=ctx_yaw)


def save_bank(bank: ProfileBank, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(bank.to_dict(), f, indent=2)
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def migrate_calibration(baseline_path: str | Path) -> Optional[Baseline]:
    """Load an existing standalone calibration.json (Stage <=10 format) so it
    can become the first profile (context unknown; caller assigns it on the
    next stable frame)."""
    from .calibration import load_baseline
    return load_baseline(baseline_path)


def profiles_path_for(baseline_path: str | Path) -> Path:
    """Profiles bank lives next to the baseline/config file."""
    return Path(baseline_path).expanduser().with_name("profiles.json")
