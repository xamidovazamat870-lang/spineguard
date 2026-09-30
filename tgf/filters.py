"""Smoothing filters: MovingAverage and OneEuroFilter."""
from __future__ import annotations

import math
from collections import deque


class MovingAverage:
    def __init__(self, n: int) -> None:
        if n <= 0:
            raise ValueError("n must be positive")
        self._n = n
        self._values: deque[float] = deque(maxlen=n)

    def update(self, x: float, t: float = 0.0) -> float:  # t ignored, API compat
        self._values.append(x)
        return sum(self._values) / len(self._values)

    def reset(self) -> None:
        self._values.clear()


class _LowPass:
    def __init__(self) -> None:
        self._y: float | None = None

    def filter(self, x: float, alpha: float) -> float:
        if self._y is None:
            self._y = x
        else:
            self._y = alpha * x + (1.0 - alpha) * self._y
        return self._y

    def reset(self) -> None:
        self._y = None


class OneEuroFilter:
    """1€ Filter — low latency, low noise; Casiez et al. 2012."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.08, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._lp_x = _LowPass()
        self._lp_dx = _LowPass()
        self._prev_t: float | None = None
        self._prev_x: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt) if dt > 0 else 1.0

    def update(self, x: float, t: float) -> float:
        dt = (t - self._prev_t) if self._prev_t is not None else 1.0 / 30.0
        dt = max(dt, 1e-6)
        dx = (x - self._prev_x) / dt if self._prev_x is not None else 0.0
        self._prev_t = t
        self._prev_x = x

        edx = self._lp_dx.filter(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._lp_x.filter(x, self._alpha(cutoff, dt))

    def reset(self) -> None:
        self._lp_x.reset()
        self._lp_dx.reset()
        self._prev_t = None
        self._prev_x = None
