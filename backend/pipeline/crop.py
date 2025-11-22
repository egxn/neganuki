import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple


@dataclass
class CropConfig:
    """Crop configuration."""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


class Cropper:
    """
    Performs cropping of frames coming from the camera pipeline.
    """

    def __init__(self, config: CropConfig = None):
        self.config = config or CropConfig()  # Default to empty config

    def update_config(self, config: CropConfig):
        """Allows dynamic runtime reconfiguration."""
        self.config = config

    def crop(self, frame: np.ndarray) -> np.ndarray:
        """
        Crop the frame according to the current config.
        If config is invalid or out-of-bounds, returns the original frame.
        """
        if frame is None or frame.size == 0:
            return frame

        if not self.config.is_valid():
            return frame

        h, w = frame.shape[:2]

        x1 = max(0, self.config.x)
        y1 = max(0, self.config.y)
        x2 = min(w, x1 + self.config.width)
        y2 = min(h, y1 + self.config.height)

        if x1 >= x2 or y1 >= y2:
            # Invalid crop region
            return frame

        return frame[y1:y2, x1:x2]

    def crop_center(self, frame: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """
        Optional helper: crops the center of the frame using a given (w, h).
        Useful for dynamically testing configs.
        """
        if frame is None or frame.size == 0:
            return frame

        h, w = frame.shape[:2]
        crop_w, crop_h = size

        if crop_w <= 0 or crop_h <= 0:
            return frame

        cx = w // 2
        cy = h // 2

        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(w, x1 + crop_w)
        y2 = min(h, y1 + crop_h)

        return frame[y1:y2, x1:x2]
