"""Image matching perception provider — OpenCV template matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from .base import PerceptionProvider, PerceptionResult, PerceptionStrategy

logger = structlog.get_logger()


@dataclass
class ImageMatch:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    center_x: int = 0
    center_y: int = 0


class ImageMatchProvider(PerceptionProvider):
    """Template matching using OpenCV for visual element detection."""

    strategy = PerceptionStrategy.IMAGE

    def __init__(self, threshold: float = 0.8) -> None:
        self._threshold = threshold

    async def locate(self, target: dict) -> PerceptionResult:
        image_ref = target.get("image_ref")
        if not image_ref:
            return PerceptionResult(strategy=self.strategy, found=False)

        screen = target.get("_image")
        if screen is None:
            from .capture import capture_screen
            screen = capture_screen(target.get("region"))

        from .capture import image_from_file
        template = image_from_file(image_ref)

        match = self.find_template(screen, template)
        if match:
            return PerceptionResult(
                strategy=self.strategy,
                found=True,
                confidence=match.confidence,
                location={
                    "x": match.center_x,
                    "y": match.center_y,
                    "width": match.width,
                    "height": match.height,
                },
            )

        return PerceptionResult(strategy=self.strategy, found=False)

    def find_template(
        self,
        screen: np.ndarray,
        template: np.ndarray,
        threshold: float | None = None,
    ) -> ImageMatch | None:
        import cv2

        threshold = threshold or self._threshold
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        logger.info("vision.match", confidence=round(max_val, 3), threshold=threshold)

        if max_val < threshold:
            return None

        h, w = template_gray.shape
        return ImageMatch(
            x=max_loc[0],
            y=max_loc[1],
            width=w,
            height=h,
            confidence=max_val,
            center_x=max_loc[0] + w // 2,
            center_y=max_loc[1] + h // 2,
        )

    def find_all_templates(
        self,
        screen: np.ndarray,
        template: np.ndarray,
        threshold: float | None = None,
        max_results: int = 20,
    ) -> list[ImageMatch]:
        import cv2

        threshold = threshold or self._threshold
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        h, w = template_gray.shape
        matches: list[ImageMatch] = []
        seen: set[tuple[int, int]] = set()

        for pt in zip(*locations[::-1]):
            grid = (pt[0] // 10, pt[1] // 10)
            if grid in seen:
                continue
            seen.add(grid)
            matches.append(ImageMatch(
                x=int(pt[0]),
                y=int(pt[1]),
                width=w,
                height=h,
                confidence=float(result[pt[1], pt[0]]),
                center_x=int(pt[0]) + w // 2,
                center_y=int(pt[1]) + h // 2,
            ))
            if len(matches) >= max_results:
                break

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
