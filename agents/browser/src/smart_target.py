"""SmartTarget — resolution-independent element targeting.

No recorded screen coordinate is ever used to click. Sources of truth:
  1. UIA on a fine-grained control (automation_id / name + control type)
  2. Recorded context image (360x200 around the cursor), multi-scale matched
  3. Recorded element image (140x50 around the cursor), multi-scale matched
  4. Vision LLM on Ollama, only if the above are not conclusive
Agreement between independent sources raises confidence; if nothing reaches
MIN_CONFIDENCE the step fails instead of clicking somewhere wrong.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass

import cv2

from .vision import Screen, capture_screen, dpi_scale, locate

logger = logging.getLogger(__name__)

try:
    from pywinauto import Desktop
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

OLLAMA_URL = "http://localhost:11434"
VISION_MODELS = ["qwen2.5vl:7b", "minicpm-v", "llava:7b", "llava:13b"]
MIN_CONFIDENCE = 0.75
AMBIGUITY_GAP = 0.03
COARSE_CONTROLS = {"Window", "Pane", "Document", "Group", "Custom", ""}
ANCHOR_MIN = 0.65        # image must already be a plausible match
ANCHOR_BOOST = 0.06
ANCHOR_TOLERANCE = 30    # px between the image match and the in-window position


@dataclass
class Candidate:
    coords: tuple[int, int]
    confidence: float
    strategy: str
    detail: str = ""


def _near(a: tuple[int, int], b: tuple[int, int], tol: int) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _uia_search(target: dict) -> Candidate | None:
    control_type = target.get("tag", "")
    if not HAS_PYWINAUTO or control_type in COARSE_CONTROLS:
        return None
    selector = target.get("selector", "")
    automation_id = selector[1:] if selector.startswith("#") else ""
    name = target.get("text", "") or target.get("name", "")
    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        return None
    for win in windows:
        try:
            if automation_id:
                el = win.child_window(auto_id=automation_id, control_type=control_type)
                if el.exists(timeout=0.2):
                    r = el.rectangle()
                    return Candidate((r.mid_point().x, r.mid_point().y), 0.95, "UIA-id", automation_id)
            if name:
                el = win.child_window(title=name, control_type=control_type, found_index=0)
                if el.exists(timeout=0.2):
                    r = el.rectangle()
                    return Candidate((r.mid_point().x, r.mid_point().y), 0.85, "UIA-name", f"{control_type}[{name}]")
        except Exception:
            continue
    return None


def _visual_search(metadata: dict, screen: Screen) -> list[Candidate]:
    recorded_dpi = metadata.get("dpi_scale") or 1.0
    prior = dpi_scale() / recorded_dpi
    out: list[Candidate] = []

    ctx_b64 = metadata.get("context_screenshot_b64", "")
    el_b64 = metadata.get("screenshot_b64", "")
    ctx = locate(ctx_b64, screen, prior) if ctx_b64 else []
    el = locate(el_b64, screen, prior) if el_b64 else []

    if ctx:
        best = ctx[0]
        ambiguous = len(ctx) > 1 and ctx[0].score - ctx[1].score < AMBIGUITY_GAP
        conf = best.score - (0.15 if ambiguous else 0.0)
        out.append(Candidate((best.x, best.y), conf, "Context-image",
                             f"score={best.score:.2f} scale={best.scale:.2f}{' ambiguous' if ambiguous else ''}"))

    if el:
        # The small element crop often matches several identical widgets; when the
        # context matched, keep the element hit closest to it to disambiguate.
        pick = el[0]
        if ctx:
            tol = int(150 * ctx[0].scale)
            near = [m for m in el if _near((m.x, m.y), (ctx[0].x, ctx[0].y), tol)]
            if near:
                pick = near[0]
        ambiguous = len(el) > 1 and el[0].score - el[1].score < AMBIGUITY_GAP and not ctx
        conf = pick.score * 0.95 - (0.2 if ambiguous else 0.0)
        out.append(Candidate((pick.x, pick.y), conf, "Element-image",
                             f"score={pick.score:.2f} scale={pick.scale:.2f}{' ambiguous' if ambiguous else ''}"))
    return out


_vision_model: str | None = None


async def _detect_vision_model() -> str | None:
    global _vision_model
    if _vision_model or not HAS_HTTPX:
        return _vision_model
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            names = {m["name"] for m in resp.json().get("models", [])}
        _vision_model = next((m for m in VISION_MODELS if m in names), None)
    except Exception:
        pass
    return _vision_model


async def _llm_search(target: dict, metadata: dict, screen: Screen) -> Candidate | None:
    model = await _detect_vision_model()
    if not model:
        return None
    ref = metadata.get("screenshot_b64", "")
    name = target.get("text", "") or target.get("name", "")
    ok, buf = cv2.imencode(".jpg", screen.image, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return None
    h, w = screen.image.shape[:2]
    prompt = (
        f"The first image is a full screenshot of {w}x{h} pixels. "
        + ("The second image shows the UI element to find (the cursor was at its center). " if ref else "")
        + (f"The element is labelled or near the text '{name}'. " if name else "")
        + 'Answer ONLY with JSON {"x": <int>, "y": <int>} giving the element center in the first image.'
    )
    images = [base64.b64encode(buf.tobytes()).decode("ascii")] + ([ref] if ref else [])
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": model, "prompt": prompt, "images": images, "stream": False,
                "options": {"temperature": 0.0, "num_predict": 64},
            })
        text = resp.json().get("response", "")
        m = re.search(r'"x"\s*:\s*(\d+)\s*,\s*"y"\s*:\s*(\d+)', text)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            if 0 <= x < w and 0 <= y < h:
                return Candidate((screen.left + x, screen.top + y), 0.70, "LLM-vision", model)
        logger.info("[SmartTarget] LLM answer not usable: %s", text[:120])
    except Exception as e:
        logger.warning("[SmartTarget] LLM vision failed: %r", e)
    return None


async def resolve_element(
    target: dict,
    metadata: dict,
    use_slow: bool = True,
    region: tuple[int, int, int, int] | None = None,
    anchor: tuple[int, int] | None = None,
) -> Candidate | None:
    """Return the best candidate above MIN_CONFIDENCE, or None (caller must fail the step).

    `region` (left, top, right, bottom) limits the visual search to the target
    application's window.
    """
    label = target.get("text") or target.get("selector") or "?"
    candidates: list[Candidate] = []

    uia = _uia_search(target)
    if uia and (region is None or (region[0] <= uia.coords[0] < region[2] and region[1] <= uia.coords[1] < region[3])):
        candidates.append(uia)

    screen = capture_screen()
    if screen is not None and region is not None:
        screen = screen.crop(*region)
    if screen is not None:
        candidates.extend(_visual_search(metadata, screen))

    # Independent sources agreeing on the same spot is the strongest signal.
    for c in candidates:
        agree = [o for o in candidates if o is not c and _near(o.coords, c.coords, 25)]
        if agree:
            c.confidence = min(0.99, max(c.confidence, max(o.confidence for o in agree)) + 0.05)
            c.detail += f" +agrees({','.join(o.strategy for o in agree)})"

    # The click's position inside its window corroborates a slightly-off image (a
    # window captured mid-animation, a notification over it). Never decisive alone.
    if anchor:
        for c in candidates:
            if c.strategy in ("Context-image", "Element-image") and c.confidence >= ANCHOR_MIN \
                    and _near(c.coords, anchor, ANCHOR_TOLERANCE):
                c.confidence = min(0.99, c.confidence + ANCHOR_BOOST)
                c.detail += " +confirmed(position in window)"

    best = max(candidates, key=lambda c: c.confidence, default=None)

    if (best is None or best.confidence < MIN_CONFIDENCE) and use_slow and screen is not None:
        llm = await _llm_search(target, metadata, screen)
        if llm:
            agree = [c for c in candidates if _near(c.coords, llm.coords, 40)]
            if agree:
                top = max(agree, key=lambda c: c.confidence)
                top.confidence = min(0.95, top.confidence + 0.2)
                top.detail += " +confirmed(LLM)"
            else:
                candidates.append(llm)
            best = max(candidates, key=lambda c: c.confidence)

    summary = ", ".join(f"{c.strategy}={c.confidence:.2f}" for c in candidates) or "none"
    if best is None or best.confidence < MIN_CONFIDENCE:
        logger.warning("[SmartTarget] '%s' NOT FOUND (candidates: %s)", label, summary)
        return None
    logger.info("[SmartTarget] '%s' → %s %.2f at %s | %s | all: %s",
                label, best.strategy, best.confidence, best.coords, best.detail, summary)
    return best
