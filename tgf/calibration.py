"""Baseline calibration from a burst of metrics."""
from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import List, Optional

from .geometry import Metrics


class CalibrationError(RuntimeError):
    """Raised when calibration lacks enough samples or movement detected."""


def _mad(values: List[float]) -> float:
    """Median Absolute Deviation."""
    if not values:
        return 0.0
    med = median(values)
    return median(abs(v - med) for v in values)


@dataclass
class Baseline:
    shoulder: float
    head: float
    lean: float
    neck: float = 0.0
    sigma_shoulder: float = 1.0
    sigma_head: float = 1.0
    sigma_neck: float = 1.0


class Calibrator:
    MAX_SIGMA = 4.0  # degrees; if noise > this, user was moving

    def __init__(self, min_samples: int = 10) -> None:
        self._min_samples = min_samples
        self._samples: List[Metrics] = []

    def add(self, m: Metrics) -> None:
        self._samples.append(m)

    @property
    def done(self) -> bool:
        return len(self._samples) >= self._min_samples

    def result(self) -> Baseline:
        if not self.done:
            raise CalibrationError(
                f"Kalibratsiya uchun yetarli namuna yo'q ({len(self._samples)}/{self._min_samples})."
            )

        def _channel(vals: List[Optional[float]]) -> tuple[float, float]:
            valid = [v for v in vals if v is not None]
            if not valid:
                return 0.0, 1.0
            med = median(valid)
            # Remove outliers (> 3*MAD from median)
            mad = _mad(valid) or 1.0
            clean = [v for v in valid if abs(v - med) <= 3.0 * mad]
            if not clean:
                clean = valid
            sigma = max(_mad(clean) * 1.4826, 0.1)  # MAD → sigma estimate
            return median(clean), sigma

        sh_med, sh_sigma = _channel([s.shoulder for s in self._samples])
        hd_med, hd_sigma = _channel([s.head for s in self._samples])
        nk_med, nk_sigma = _channel([s.neck for s in self._samples])
        ln_med, _ = _channel([s.lean for s in self._samples])

        # Warn if too much movement
        if max(sh_sigma, hd_sigma, nk_sigma) > self.MAX_SIGMA:
            raise CalibrationError("Qimirlamay o'tiring — kalibratsiya paytida harakat aniqlandi.")

        return Baseline(
            shoulder=sh_med, head=hd_med, lean=ln_med, neck=nk_med,
            sigma_shoulder=sh_sigma, sigma_head=hd_sigma, sigma_neck=nk_sigma,
        )


def load_baseline(path: str | Path) -> Optional[Baseline]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        vals = {k: float(data[k]) for k in ("shoulder", "head", "lean")}
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None
    if not all(math.isfinite(v) for v in vals.values()):
        return None
    # Graceful load if sigma fields absent (old format)
    return Baseline(
        shoulder=vals["shoulder"],
        head=vals["head"],
        lean=vals["lean"],
        neck=float(data.get("neck", 0.0)),
        sigma_shoulder=float(data.get("sigma_shoulder", 1.0)),
        sigma_head=float(data.get("sigma_head", 1.0)),
        sigma_neck=float(data.get("sigma_neck", 1.0)),
    )


def save_baseline(baseline: Baseline, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(baseline), f, indent=2)
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
