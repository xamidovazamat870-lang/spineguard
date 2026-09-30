"""LatestFrameGrabber: daemon thread that keeps only the newest camera frame."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Frame:
    data: np.ndarray
    ts: float
    seq: int


class LatestFrameGrabber:
    """Background thread; exposes only the latest frame via get_new()."""

    def __init__(self, cap, fps: float) -> None:
        self._cap = cap
        self._interval = 1.0 / fps if fps > 0 else 0.0
        self._latest: Optional[Frame] = None
        self._lock = threading.Lock()
        self._seq = 0
        self._errors = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            t0 = time.monotonic()
            if not self._cap.grab():
                self._errors += 1
                time.sleep(0.05)
                continue
            ok, frame = self._cap.retrieve()
            if not ok or frame is None:
                self._errors += 1
                time.sleep(0.05)
                continue
            self._errors = 0
            ts = time.monotonic()
            with self._lock:
                self._seq += 1
                self._latest = Frame(data=frame, ts=ts, seq=self._seq)
            elapsed = time.monotonic() - t0
            rem = self._interval - elapsed
            if rem > 0:
                time.sleep(rem)

    def get_new(self, last_seq: int) -> Optional[Frame]:
        with self._lock:
            if self._latest is None or self._latest.seq == last_seq:
                return None
            return self._latest

    def set_fps(self, fps: float) -> None:
        self._interval = 1.0 / fps if fps > 0 else 0.0

    @property
    def error_count(self) -> int:
        return self._errors

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
