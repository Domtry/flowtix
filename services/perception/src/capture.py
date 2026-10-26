"""Screen and region capture utilities."""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()


def capture_screen(region: dict[str, int] | None = None) -> np.ndarray:
    """Capture the screen or a region, return as BGR numpy array (OpenCV format)."""
    import mss

    with mss.mss() as sct:
        if region:
            monitor = {
                "left": region.get("x", 0),
                "top": region.get("y", 0),
                "width": region.get("width", 1920),
                "height": region.get("height", 1080),
            }
        else:
            monitor = sct.monitors[1]

        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        # mss returns BGRA, convert to BGR
        return img[:, :, :3].copy()


def capture_to_bytes(region: dict[str, int] | None = None, fmt: str = "png") -> bytes:
    """Capture screen and return as encoded image bytes."""
    import cv2

    img = capture_screen(region)
    success, buffer = cv2.imencode(f".{fmt}", img)
    if not success:
        raise RuntimeError("Failed to encode screenshot")
    return buffer.tobytes()


def image_from_file(path: str) -> np.ndarray:
    """Load an image from file as BGR numpy array."""
    import cv2

    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    return img


def image_to_gray(img: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale."""
    import cv2
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
