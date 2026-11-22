"""Small-area desktop capture using MSS."""
from __future__ import annotations

import numpy as np
import mss

from app.config.settings import Region


class ScreenCapture:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def capture(self, region: Region) -> np.ndarray:
        monitor = {
            "left": int(region.x),
            "top": int(region.y),
            "width": int(region.width),
            "height": int(region.height),
        }
        shot = self._sct.grab(monitor)
        bgra = np.asarray(shot, dtype=np.uint8)
        return bgra[:, :, :3][:, :, ::-1].copy()

    def close(self) -> None:
        self._sct.close()
