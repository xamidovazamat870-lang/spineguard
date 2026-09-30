"""Webcam capture via LatestFrameGrabber background thread."""
from __future__ import annotations

import sys
from typing import Optional

import numpy as np

from .config import Config

_NOPOSE_CAP_FPS = 5


class CameraError(RuntimeError):
    """Raised when the camera cannot be opened."""


class Camera:
    def __init__(self, cfg: Config) -> None:
        import cv2
        self.cfg = cfg
        if sys.platform == "darwin":
            self._cap = cv2.VideoCapture(cfg.camera_index, cv2.CAP_AVFOUNDATION)
        else:
            self._cap = cv2.VideoCapture(cfg.camera_index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraError(
                f"Kamera {cfg.camera_index} ochilmadi. macOS: Tizim sozlamalari > "
                "Maxfiylik va xavfsizlik > Kamera bo'limida terminal/ilovaga ruxsat bering; "
                "boshqa ilova kamerani band qilmaganini tekshiring."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)

        from .capture import LatestFrameGrabber
        self._grabber = LatestFrameGrabber(self._cap, cfg.capture_fps)
        self._last_seq = 0
        self._width = cfg.width

    def set_fps(self, fps: float) -> None:
        self._grabber.set_fps(fps)

    def read(self) -> Optional[np.ndarray]:
        import cv2
        frame_obj = self._grabber.get_new(self._last_seq)
        if frame_obj is None:
            return None
        self._last_seq = frame_obj.seq
        frame = frame_obj.data
        h, w = frame.shape[:2]
        if w > self._width:
            frame = cv2.resize(frame, (self._width, max(1, round(h * self._width / w))))
        return frame

    def close(self) -> None:
        try:
            self._grabber.stop()
        except Exception:
            pass
        try:
            self._cap.release()
        except Exception:
            pass
