"""Pure geometry helpers for pose landmarks."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees
from typing import NamedTuple, Optional


class Point(NamedTuple):
    x: float
    y: float
    visibility: float = 1.0


class Landmarks(NamedTuple):
    left_shoulder: Point
    right_shoulder: Point
    left_ear: Point
    right_ear: Point
    nose: Optional[Point] = None
    left_eye: Optional[Point] = None
    right_eye: Optional[Point] = None


class Point3D(NamedTuple):
    x: float
    y: float
    z: float


class Landmarks3D(NamedTuple):
    nose: Point3D
    left_shoulder: Point3D
    right_shoulder: Point3D
    left_ear: Point3D
    right_ear: Point3D


@dataclass
class PoseContext:
    cx: float                       # mid-shoulder x, 0..1 (mirror-agnostic raw MP coord)
    scale: float                    # shoulder width / frame width
    body_yaw_deg: Optional[float]   # from 3D shoulder vector; None if no 3D
    head_yaw_proxy: float           # (nose.x - mid_ear.x) / ear_width
    edge: bool                      # shoulders/ears close to frame edge


@dataclass
class Metrics:
    shoulder: Optional[float]  # roll of shoulder line (None if not visible)
    head: Optional[float]      # roll of ear line (None if not visible)
    neck: Optional[float]      # mid-shoulder→mid-ear vector angle from vertical (None if not visible)
    lean: Optional[float]      # lateral lean ratio (kept for display; None if not visible)
    # Stage 14: yaw-invariant 3D counterparts (None unless world landmarks were supplied)
    shoulder_yaw_invariant: Optional[float] = None  # roll3d_deg(left_shoulder, right_shoulder)
    neck_yaw_invariant: Optional[float] = None      # neck3d_deg(ears, shoulders)


def _normalize_angle(deg: float) -> float:
    while deg <= -90.0:
        deg += 180.0
    while deg > 90.0:
        deg -= 180.0
    return deg


def roll_deg(a: Point, b: Point, aspect: float = 1.0) -> float:
    """Roll angle from point a (left) to point b (right).

    Positive = left side lower = "LEFT" lean.
    Landmarks are normalized to [0,1] per axis, so x must be scaled by
    aspect (= frame width / height) to get the true pixel-space angle.
    """
    raw = degrees(atan2(a.y - b.y, (a.x - b.x) * aspect))
    return _normalize_angle(raw)


def neck_deg(l_ear: Point, r_ear: Point, l_sh: Point, r_sh: Point, aspect: float = 1.0) -> float:
    """Angle of the mid-shoulder→mid-ear vector from vertical (in pixel space).

    Positive = leans left, negative = leans right.
    """
    mid_ear_x = (l_ear.x + r_ear.x) / 2.0
    mid_ear_y = (l_ear.y + r_ear.y) / 2.0
    mid_sh_x = (l_sh.x + r_sh.x) / 2.0
    mid_sh_y = (l_sh.y + r_sh.y) / 2.0
    dx = (mid_ear_x - mid_sh_x) * aspect
    dy = mid_sh_y - mid_ear_y  # positive = ear is above shoulder
    if dy == 0:
        return 0.0
    return _normalize_angle(degrees(atan2(dx, dy)))


def lean_ratio(l_ear: Point, r_ear: Point, l_sh: Point, r_sh: Point) -> float:
    mid_ear_x = (l_ear.x + r_ear.x) / 2.0
    mid_sh_x = (l_sh.x + r_sh.x) / 2.0
    shoulder_width = abs(l_sh.x - r_sh.x)
    if shoulder_width == 0:
        return 0.0
    return (mid_ear_x - mid_sh_x) / shoulder_width


def roll3d_deg(a3: Point3D, b3: Point3D) -> float:
    """Yaw-invariant roll from 3D point a (left) to b (right).

    Uses atan2(dy, hypot(dx, dz)) so rotation about the vertical (Y) axis
    (yaw, dz component absorbed into the horizontal magnitude) does not
    change the result. Sign convention matches roll_deg: positive = left lower.
    Assumes 3D axes are camera-aligned (X right, Y down, Z toward camera),
    as provided by MediaPipe pose_world_landmarks.
    """
    from math import hypot
    dx = a3.x - b3.x
    dy = a3.y - b3.y
    dz = a3.z - b3.z
    return _normalize_angle(degrees(atan2(dy, hypot(dx, dz))))


def neck3d_deg(l_ear: Point3D, r_ear: Point3D, l_sh: Point3D, r_sh: Point3D) -> float:
    """3D variant of neck_deg: mid-shoulder->mid-ear vector angle from vertical,
    projected onto the horizontal-magnitude/vertical plane (yaw-invariant)."""
    from math import hypot
    mid_ear = Point3D((l_ear.x + r_ear.x) / 2.0, (l_ear.y + r_ear.y) / 2.0, (l_ear.z + r_ear.z) / 2.0)
    mid_sh = Point3D((l_sh.x + r_sh.x) / 2.0, (l_sh.y + r_sh.y) / 2.0, (l_sh.z + r_sh.z) / 2.0)
    dx = mid_ear.x - mid_sh.x
    dz = mid_ear.z - mid_sh.z
    dy = mid_sh.y - mid_ear.y  # positive = ear above shoulder
    if dy == 0:
        return 0.0
    return _normalize_angle(degrees(atan2(hypot(dx, dz), dy)) * (1 if dx >= 0 else -1))


def compute_pose_context(
    lm: Landmarks,
    lm3: Optional["Landmarks3D"],
    frame_edge_margin: float = 0.08,
) -> PoseContext:
    """Per-frame yaw/edge context, independent of channel visibility gating."""
    ls, rs, le, re = lm.left_shoulder, lm.right_shoulder, lm.left_ear, lm.right_ear
    cx = (ls.x + rs.x) / 2.0
    scale = abs(ls.x - rs.x)

    body_yaw_deg: Optional[float] = None
    if lm3 is not None:
        dx = lm3.left_shoulder.x - lm3.right_shoulder.x
        dz = lm3.left_shoulder.z - lm3.right_shoulder.z
        body_yaw_deg = degrees(atan2(dz, dx))

    ear_width = abs(le.x - re.x)
    mid_ear_x = (le.x + re.x) / 2.0
    nose_x = lm.nose.x if lm.nose is not None else mid_ear_x
    head_yaw_proxy = (nose_x - mid_ear_x) / ear_width if ear_width > 1e-6 else 0.0

    edge = any(
        p.x < frame_edge_margin or p.x > (1.0 - frame_edge_margin)
        for p in (ls, rs, le, re)
    )
    return PoseContext(cx=cx, scale=scale, body_yaw_deg=body_yaw_deg,
                        head_yaw_proxy=head_yaw_proxy, edge=edge)


def _vis(p: Point, vmin: float) -> bool:
    return p.visibility >= vmin


def compute_metrics(
    lm: Landmarks,
    visibility_min: float = 0.5,
    visibility_min_shoulder: float = 0.35,
    aspect: float = 1.0,
    lm3: Optional["Landmarks3D"] = None,
) -> Optional[Metrics]:
    """Compute per-channel metrics; returns None only if ALL channels are invalid.

    lm3: optional world (metric, yaw-invariant) 3D landmarks. When provided,
    shoulder_yaw_invariant/neck_yaw_invariant are additionally populated from
    roll3d_deg/neck3d_deg. This does not affect the existing 2D fields.
    """
    ls, rs, le, re = lm.left_shoulder, lm.right_shoulder, lm.left_ear, lm.right_ear
    # Frontal holatda quloqlar ko'rinmaydi (MediaPipe ularni og'iz/jag'ga qo'yadi) -> ko'z chizig'i barqarorroq
    if lm.left_eye is not None and lm.right_eye is not None \
            and _vis(lm.left_eye, visibility_min) and _vis(lm.right_eye, visibility_min):
        le, re = lm.left_eye, lm.right_eye

    sh_ok = _vis(ls, visibility_min_shoulder) and _vis(rs, visibility_min_shoulder)
    ear_ok = _vis(le, visibility_min) and _vis(re, visibility_min)
    neck_ok = sh_ok and ear_ok

    if not sh_ok and not ear_ok:
        return None  # truly nothing usable

    shoulder = roll_deg(ls, rs, aspect) if sh_ok else None
    head = roll_deg(le, re, aspect) if ear_ok else None
    neck = neck_deg(le, re, ls, rs, aspect) if neck_ok else None
    lean = lean_ratio(le, re, ls, rs) if neck_ok else None

    shoulder_yaw_invariant: Optional[float] = None
    neck_yaw_invariant: Optional[float] = None
    if lm3 is not None:
        if sh_ok:
            shoulder_yaw_invariant = roll3d_deg(lm3.left_shoulder, lm3.right_shoulder)
        if neck_ok:
            neck_yaw_invariant = neck3d_deg(
                lm3.left_ear, lm3.right_ear, lm3.left_shoulder, lm3.right_shoulder
            )

    return Metrics(
        shoulder=shoulder, head=head, neck=neck, lean=lean,
        shoulder_yaw_invariant=shoulder_yaw_invariant,
        neck_yaw_invariant=neck_yaw_invariant,
    )
