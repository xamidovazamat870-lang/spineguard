"""Debug overlay drawing."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .geometry import Landmarks, Metrics, PoseContext

_COLORS = {
    "Normal": (0, 200, 0),
    "Tilt Left": (0, 0, 255),
    "Tilt Right": (0, 0, 255),
    "NoPose": (150, 150, 150),
    "Turned": (0, 165, 255),
}


def _px(p, w: int, h: int) -> tuple[int, int]:
    return int(p.x * w), int(p.y * h)


def draw(
    frame: np.ndarray,
    lm: Optional[Landmarks],
    metrics: Optional[Metrics],
    state: str,
    extra: str = "",
    ctx: Optional[PoseContext] = None,
    label: Optional[str] = None,
) -> np.ndarray:
    """`state` selects the color (must be a key of _COLORS / VALID_STATUSES);
    `label` is the on-screen text (defaults to `state`) so callers may localize."""
    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    color = _COLORS.get(state, (255, 255, 255))
    label = label if label is not None else state

    if lm is not None:
        ls = _px(lm.left_shoulder, w, h)
        rs = _px(lm.right_shoulder, w, h)
        hl = lm.left_eye if (lm.left_eye and lm.right_eye and lm.left_eye.visibility >= 0.5 and lm.right_eye.visibility >= 0.5) else lm.left_ear
        hr = lm.right_eye if hl is lm.left_eye else lm.right_ear
        le = _px(hl, w, h)
        re = _px(hr, w, h)
        ls, rs, le, re = (w - ls[0], ls[1]), (w - rs[0], rs[1]), (w - le[0], le[1]), (w - re[0], re[1])
        cv2.line(frame, ls, rs, color, 2)
        cv2.line(frame, le, re, color, 2)
        for pt in (ls, rs, le, re):
            cv2.circle(frame, pt, 4, color, -1)

    if metrics is not None:
        def _fmt(v): return f"{v:.1f}" if v is not None else "—"
        text = (f"sh={_fmt(metrics.shoulder)} hd={_fmt(metrics.head)} "
                f"nk={_fmt(metrics.neck)} ln={_fmt(metrics.lean)}")
        cv2.putText(frame, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    cv2.putText(frame, label, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    if ctx is not None:
        by = f"{ctx.body_yaw_deg:.0f}" if ctx.body_yaw_deg is not None else "—"
        ctx_text = (f"cx={ctx.cx:.2f} scale={ctx.scale:.2f} yaw={by} "
                    f"hyaw={ctx.head_yaw_proxy:.2f}{' EDGE' if ctx.edge else ''}")
        cv2.putText(frame, ctx_text, (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 0), 1, cv2.LINE_AA)
    if extra:
        cv2.putText(frame, extra, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
    return frame
