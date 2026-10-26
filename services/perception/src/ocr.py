"""OCR perception provider — PaddleOCR primary, Tesseract fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from .base import PerceptionProvider, PerceptionResult, PerceptionStrategy

logger = structlog.get_logger()


@dataclass
class OcrMatch:
    text: str
    confidence: float
    bbox: list[list[int]]
    center_x: int = 0
    center_y: int = 0


class OcrProvider(PerceptionProvider):
    """OCR-based element detection. Uses PaddleOCR if available, falls back to Tesseract."""

    strategy = PerceptionStrategy.OCR

    def __init__(self, engine: str = "auto", lang: str = "fr") -> None:
        self._engine = engine
        self._lang = lang
        self._paddle_ocr: Any = None
        self._initialized = False

    def _init_engine(self) -> str:
        if self._engine == "paddle" or self._engine == "auto":
            try:
                from paddleocr import PaddleOCR
                self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang=self._lang, show_log=False)
                self._initialized = True
                logger.info("ocr.init", engine="paddleocr")
                return "paddle"
            except ImportError:
                if self._engine == "paddle":
                    raise
        if self._engine == "tesseract" or self._engine == "auto":
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._initialized = True
                logger.info("ocr.init", engine="tesseract")
                return "tesseract"
            except Exception:
                if self._engine == "tesseract":
                    raise
        raise RuntimeError("No OCR engine available (install paddleocr or pytesseract)")

    async def locate(self, target: dict) -> PerceptionResult:
        search_text = target.get("text", "")
        if not search_text:
            return PerceptionResult(strategy=self.strategy, found=False)

        image = target.get("_image")
        if image is None:
            from .capture import capture_screen
            image = capture_screen(target.get("region"))

        matches = self.detect_text(image)
        for match in matches:
            if search_text.lower() in match.text.lower():
                return PerceptionResult(
                    strategy=self.strategy,
                    found=True,
                    text=match.text,
                    confidence=match.confidence,
                    location={
                        "x": match.center_x,
                        "y": match.center_y,
                        "bbox": match.bbox,
                    },
                )

        return PerceptionResult(strategy=self.strategy, found=False, text=search_text)

    def detect_text(self, image: np.ndarray) -> list[OcrMatch]:
        if not self._initialized:
            engine = self._init_engine()
        else:
            engine = "paddle" if self._paddle_ocr else "tesseract"

        if engine == "paddle":
            return self._detect_paddle(image)
        return self._detect_tesseract(image)

    def _detect_paddle(self, image: np.ndarray) -> list[OcrMatch]:
        result = self._paddle_ocr.ocr(image, cls=True)
        matches: list[OcrMatch] = []
        if not result or not result[0]:
            return matches

        for line in result[0]:
            bbox = line[0]
            text = line[1][0]
            confidence = line[1][1]
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            matches.append(OcrMatch(
                text=text,
                confidence=confidence,
                bbox=[[int(x) for x in pt] for pt in bbox],
                center_x=int(sum(xs) / len(xs)),
                center_y=int(sum(ys) / len(ys)),
            ))

        logger.info("ocr.detect", engine="paddle", matches=len(matches))
        return matches

    def _detect_tesseract(self, image: np.ndarray) -> list[OcrMatch]:
        import pytesseract

        from .capture import image_to_gray
        gray = image_to_gray(image)

        data = pytesseract.image_to_data(gray, lang=self._lang, output_type=pytesseract.Output.DICT)
        matches: list[OcrMatch] = []

        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            conf = float(data["conf"][i])
            if conf < 30:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            matches.append(OcrMatch(
                text=text.strip(),
                confidence=conf / 100,
                bbox=[[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                center_x=x + w // 2,
                center_y=y + h // 2,
            ))

        logger.info("ocr.detect", engine="tesseract", matches=len(matches))
        return matches

    def extract_all_text(self, image: np.ndarray) -> str:
        matches = self.detect_text(image)
        return " ".join(m.text for m in matches)
