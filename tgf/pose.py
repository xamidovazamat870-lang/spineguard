"""MediaPipe Pose wrapper producing Landmarks."""
from __future__ import annotations

from typing import Optional

import numpy as np

from .config import Config
from .geometry import Landmarks, Landmarks3D, Point, Point3D

_NOSE, _L_SHOULDER, _R_SHOULDER, _L_EAR, _R_EAR = 0, 11, 12, 7, 8
_L_EYE, _R_EYE = 2, 5


class PoseEstimator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        import cv2  # noqa: F401  (lazy import keeps sandbox import-safe)
        import mediapipe as mp
        if not hasattr(mp, "solutions"):
            raise RuntimeError(
                "Bu mediapipe versiyasida mp.solutions yo'q. "
                "`pip install -e .` bilan mos versiyani o'rnating (mediapipe<=0.10.21)."
            )
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=cfg.model_complexity,
            smooth_landmarks=cfg.mp_smooth,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._face = None
        try:
            self._face = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False, max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.5, min_tracking_confidence=0.5,
            )
        except Exception:
            self._face = None

    def _face_eyes(self, rgb):
        """Face Mesh'dan aniq ko'z markazlari (chap, o'ng); topilmasa None."""
        if self._face is None:
            return None
        try:
            res = self._face.process(rgb)
            if not res.multi_face_landmarks:
                return None
            f = res.multi_face_landmarks[0].landmark
            def c(a, b):
                return Point((f[a].x + f[b].x) / 2.0, (f[a].y + f[b].y) / 2.0, 1.0)
            return c(263, 362), c(33, 133)  # subyektning chap / o'ng ko'zi
        except Exception:
            return None

    def process(self, frame: np.ndarray) -> Optional[Landmarks]:
        lm, _ = self.process_full(frame)
        return lm

    def process_full(self, frame: np.ndarray) -> tuple[Optional[Landmarks], Optional[Landmarks3D]]:
        """Like process(), but also returns world (metric, yaw-invariant) 3D landmarks
        when available (requires cfg.use_world and the model providing them)."""
        import cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return None, None
        lm = result.pose_landmarks.landmark
        try:
            pts = {
                idx: Point(lm[idx].x, lm[idx].y, lm[idx].visibility)
                for idx in (_NOSE, _L_SHOULDER, _R_SHOULDER, _L_EAR, _R_EAR, _L_EYE, _R_EYE)
            }
        except IndexError:
            return None, None
        landmarks = Landmarks(
            left_shoulder=pts[_L_SHOULDER],
            right_shoulder=pts[_R_SHOULDER],
            left_ear=pts[_L_EAR],
            right_ear=pts[_R_EAR],
            nose=pts[_NOSE],
            left_eye=pts[_L_EYE],
            right_eye=pts[_R_EYE],
        )
        eyes = self._face_eyes(rgb)
        if eyes is not None:
            landmarks = landmarks._replace(left_eye=eyes[0], right_eye=eyes[1])

        landmarks3: Optional[Landmarks3D] = None
        if getattr(self.cfg, "use_world", False):
            world = getattr(result, "pose_world_landmarks", None)
            if world is not None:
                wl = world.landmark
                try:
                    landmarks3 = Landmarks3D(
                        nose=Point3D(wl[_NOSE].x, wl[_NOSE].y, wl[_NOSE].z),
                        left_shoulder=Point3D(wl[_L_SHOULDER].x, wl[_L_SHOULDER].y, wl[_L_SHOULDER].z),
                        right_shoulder=Point3D(wl[_R_SHOULDER].x, wl[_R_SHOULDER].y, wl[_R_SHOULDER].z),
                        left_ear=Point3D(wl[_L_EAR].x, wl[_L_EAR].y, wl[_L_EAR].z),
                        right_ear=Point3D(wl[_R_EAR].x, wl[_R_EAR].y, wl[_R_EAR].z),
                    )
                except IndexError:
                    landmarks3 = None
        return landmarks, landmarks3

    def close(self) -> None:
        try:
            if self._face is not None:
                self._face.close()
        except Exception:
            pass
        try:
            self._pose.close()
        except Exception:
            pass
