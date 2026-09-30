"""Non-blocking macOS alerts with cooldown, sound selection, volume, and repeat."""
from __future__ import annotations

import subprocess
import time
from typing import Callable, List, Optional

from .config import Config
from .sounds import resolve_sound

_FALLBACK_SOUND = "Tink"


class Alerter:
    def __init__(self, cfg: Config, clock: Callable[[], float] = time.monotonic) -> None:
        self.cfg = cfg
        self._clock = clock
        self._last_fire: Optional[float] = None
        self._children: List[subprocess.Popen] = []
        # Pending-repeat state for the current "fire" series.
        self._pending_spec: Optional[str] = None
        self._pending_count: int = 0
        self._next_repeat_at: Optional[float] = None

    def _reap(self) -> None:
        """Collect finished afplay processes (no zombies); notify if sound failed."""
        alive = []
        for p in self._children:
            rc = p.poll()
            if rc is None:
                alive.append(p)
            elif isinstance(rc, int) and rc != 0:
                self._notify_fallback()
        self._children = alive

    def _spec_for(self, side: Optional[str]) -> str:
        if side == "left" and self.cfg.sound_left:
            return self.cfg.sound_left
        if side == "right" and self.cfg.sound_right:
            return self.cfg.sound_right
        return self.cfg.sound or _FALLBACK_SOUND

    def _play(self, spec: str) -> None:
        path = resolve_sound(spec)
        if path is None and spec != _FALLBACK_SOUND:
            path = resolve_sound(_FALLBACK_SOUND)
        if path is None:
            self._notify_fallback()
            return
        try:
            self._children.append(
                subprocess.Popen(
                    ["afplay", "-v", str(self.cfg.volume), str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        except (OSError, FileNotFoundError):
            self._notify_fallback()

    def fire(self, side: Optional[str] = None) -> bool:
        """Start (or suppress, if in cooldown) one alert series of cfg.repeat plays."""
        self._reap()
        now = self._clock()
        if self._last_fire is not None and (now - self._last_fire) < self.cfg.cooldown_sec:
            return False
        self._last_fire = now
        spec = self._spec_for(side)
        self._play(spec)
        self._pending_spec = spec
        self._pending_count = max(self.cfg.repeat, 1) - 1
        self._next_repeat_at = now + self.cfg.repeat_gap_sec if self._pending_count > 0 else None
        return True

    def tick(self, now: float) -> None:
        """Call every loop iteration to advance pending repeats (no threads)."""
        self._reap()
        if self._pending_count <= 0 or self._next_repeat_at is None:
            return
        if now >= self._next_repeat_at:
            self._play(self._pending_spec or _FALLBACK_SOUND)
            self._pending_count -= 1
            self._next_repeat_at = now + self.cfg.repeat_gap_sec if self._pending_count > 0 else None

    def preview(self, spec: str) -> None:
        """Play a sound once, ignoring cooldown (for the --test-sound / 's' key flow)."""
        self._play(spec)

    def _notify_fallback(self) -> None:
        try:
            subprocess.Popen(
                ["osascript", "-e", 'display notification "Yomon holat!" with title "TGF"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, FileNotFoundError):
            pass
