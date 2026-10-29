"""Vision utilities — resolution-independent element capture and matching.

The recorded image of the element is the ground truth. Matching is multi-scale so
it survives DPI scaling changes, zoom and different machines.
"""

import base64
import ctypes
import logging
from dataclasses import dataclass

import cv2
import numpy as np

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

logger = logging.getLogger(__name__)

# Physical pixels everywhere: hooks, screenshots and SendInput must agree.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

ELEMENT_HALF_W, ELEMENT_HALF_H = 70, 25
CONTEXT_HALF_W, CONTEXT_HALF_H = 180, 100


def dpi_scale() -> float:
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


def _grab(left: int, top: int, width: int, height: int) -> np.ndarray | None:
    if not HAS_MSS:
        return None
    with mss.mss() as sct:
        img = sct.grab({"left": left, "top": top, "width": width, "height": height})
        return np.array(img)[:, :, :3].copy()


def _encode(arr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", arr)
    return base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""


def _decode(b64: str) -> np.ndarray | None:
    try:
        return cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


class SnapshotGrabber:
    """Fast crops around the cursor from inside the input hook, so the image is the
    screen at the exact click instant (menus close a few ms later). mss handles are
    thread-bound: create and use this in one thread only."""

    def __init__(self) -> None:
        self._sct = mss.mss() if HAS_MSS else None

    def grab(self, x: int, y: int) -> tuple[np.ndarray | None, np.ndarray | None]:
        if self._sct is None:
            return None, None
        try:
            ctx = np.array(self._sct.grab({
                "left": x - CONTEXT_HALF_W, "top": y - CONTEXT_HALF_H,
                "width": 2 * CONTEXT_HALF_W, "height": 2 * CONTEXT_HALF_H,
            }))[:, :, :3]
            ox, oy = CONTEXT_HALF_W - ELEMENT_HALF_W, CONTEXT_HALF_H - ELEMENT_HALF_H
            el = ctx[oy:oy + 2 * ELEMENT_HALF_H, ox:ox + 2 * ELEMENT_HALF_W].copy()
            return el, ctx.copy()
        except Exception:
            return None, None


def encode_snapshot(el: np.ndarray | None, ctx: np.ndarray | None) -> dict:
    snap: dict = {"dpi_scale": dpi_scale()}
    if el is not None:
        snap["element_b64"] = _encode(el)
    if ctx is not None:
        snap["context_b64"] = _encode(ctx)
    return snap


def capture_click_snapshot(x: int, y: int) -> dict:
    """Capture two crops centered on the click point plus the DPI used at record time.

    Because both crops are centered on the cursor, the click point is always the
    crop center: no screen coordinates are needed at replay.
    """
    snap: dict = {"dpi_scale": dpi_scale()}
    try:
        el = _grab(x - ELEMENT_HALF_W, y - ELEMENT_HALF_H, 2 * ELEMENT_HALF_W, 2 * ELEMENT_HALF_H)
        ctx = _grab(x - CONTEXT_HALF_W, y - CONTEXT_HALF_H, 2 * CONTEXT_HALF_W, 2 * CONTEXT_HALF_H)
        if el is not None:
            snap["element_b64"] = _encode(el)
        if ctx is not None:
            snap["context_b64"] = _encode(ctx)
    except Exception as e:
        logger.warning("capture_click_snapshot failed: %s", e)
    return snap


def _edges(gray: np.ndarray) -> np.ndarray:
    """Gradient magnitude: identical for black-on-white and white-on-blue text, so a
    menu item recorded while highlighted still matches when it is not (and vice versa)."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


@dataclass
class Screen:
    image: np.ndarray
    gray: np.ndarray
    left: int
    top: int
    _edges: np.ndarray | None = None

    @property
    def edges(self) -> np.ndarray:
        if self._edges is None:
            self._edges = _edges(self.gray)
        return self._edges

    def crop(self, left: int, top: int, right: int, bottom: int) -> "Screen":
        """Restrict to a screen-coordinate rectangle (e.g. the target app window) so
        look-alikes elsewhere — another monitor, another app — can't be matched."""
        h, w = self.gray.shape[:2]
        x0, y0 = max(0, left - self.left), max(0, top - self.top)
        x1, y1 = min(w, right - self.left), min(h, bottom - self.top)
        if x1 - x0 < 20 or y1 - y0 < 20:
            return self
        return Screen(self.image[y0:y1, x0:x1], self.gray[y0:y1, x0:x1],
                      self.left + x0, self.top + y0)


def capture_screen() -> Screen | None:
    """Capture the whole virtual screen (all monitors) with its origin offset."""
    if not HAS_MSS:
        return None
    try:
        with mss.mss() as sct:
            mon = sct.monitors[0]
            arr = np.array(sct.grab(mon))[:, :, :3].copy()
            return Screen(arr, cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY), mon["left"], mon["top"])
    except Exception as e:
        logger.warning("capture_screen failed: %s", e)
        return None


@dataclass
class Match:
    x: int
    y: int
    score: float
    scale: float


def _match(image: np.ndarray, tpl: np.ndarray) -> np.ndarray:
    """TM_CCOEFF_NORMED with flat image windows zeroed: their variance is ~0 and the
    normalisation then yields spurious 1.0 peaks (blank areas, empty edge maps)."""
    image = image.astype(np.float32)
    tpl = tpl.astype(np.float32)
    res = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
    th, tw = tpl.shape[:2]
    mean = cv2.boxFilter(image, cv2.CV_32F, (tw, th), normalize=True, borderType=cv2.BORDER_CONSTANT)
    sq = cv2.boxFilter(image * image, cv2.CV_32F, (tw, th), normalize=True, borderType=cv2.BORDER_CONSTANT)
    var = sq - mean * mean
    # boxFilter is centred; matchTemplate indexes windows by their top-left corner
    oy, ox = th // 2, tw // 2
    var = var[oy:oy + res.shape[0], ox:ox + res.shape[1]]
    tpl_std = float(tpl.std())
    res[(var < max(1e-3, (tpl_std * 0.2) ** 2)) | ~np.isfinite(res)] = 0
    return res


def _scales(prior: float) -> list[float]:
    sweep = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.5, 1.75, 2.0]
    ordered = [prior] + sorted(sweep, key=lambda s: abs(s - prior))
    seen, out = set(), []
    for s in ordered:
        k = round(s, 3)
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def locate(template_b64: str, screen: Screen, scale_prior: float = 1.0, top_k: int = 3) -> list[Match]:
    """Multi-scale template matching. Returns the best distinct matches, best first,
    in real screen coordinates (virtual-screen origin applied)."""
    tpl = _decode(template_b64)
    if tpl is None:
        return []
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    sh, sw = screen.gray.shape[:2]

    best_scale, best_score, best_map, best_size = 1.0, -1.0, None, (0, 0)
    for s in _scales(scale_prior):
        th, tw = int(tpl_gray.shape[0] * s), int(tpl_gray.shape[1] * s)
        if th < 10 or tw < 10 or th >= sh or tw >= sw:
            continue
        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
        t = cv2.resize(tpl_gray, (tw, th), interpolation=interp)
        res = _match(screen.gray, t)
        _, mx, _, _ = cv2.minMaxLoc(res)
        if mx < 0.9:
            # Appearance differs (hover highlight, selection): compare shapes instead.
            res = np.maximum(res, _match(screen.edges, _edges(t)))
            _, mx, _, _ = cv2.minMaxLoc(res)
        if mx > best_score:
            best_scale, best_score, best_map, best_size = s, mx, res, (tw, th)
        # The DPI ratio predicts the scale; only sweep others if it clearly failed.
        if mx >= 0.75 and s == scale_prior:
            break
        if mx >= 0.97:
            break

    if best_map is None:
        return []

    tw, th = best_size
    res = best_map.copy()
    matches: list[Match] = []
    for _ in range(top_k):
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx < 0.5:
            break
        matches.append(Match(
            screen.left + loc[0] + tw // 2,
            screen.top + loc[1] + th // 2,
            float(mx), best_scale,
        ))
        # suppress this peak so the next one is a genuinely different place
        x0, y0 = max(0, loc[0] - tw // 2), max(0, loc[1] - th // 2)
        res[y0:loc[1] + th // 2 + 1, x0:loc[0] + tw // 2 + 1] = -1
    return matches
