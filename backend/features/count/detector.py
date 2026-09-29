"""Bird detection on a photo, with the maths kept out of the router.

WHY A GENERAL DETECTOR
----------------------
This runs YOLO11n and keeps only COCO class 14, "bird". It is not trained on
chickens specifically, so it is good at a bird standing clear of the flock and
poor at one half-hidden behind another. That limitation is real and the feature
is built around admitting it rather than hiding it.

WHY NO 100% CLAIM
-----------------
Birds overlap, face away, stand behind feeders and walk out of frame. On a
dense barn photo the honest answer changes with the confidence threshold:
the same image yields 9 birds at 0.25 and 17 at 0.10. A single number with no
error bar would be a lie dressed as precision, so this module returns a range
and a quality flag, and the feature asks the farmer to confirm.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

BIRD_CLASS = 14           # COCO "bird"
INPUT_SIZE = 640
CONF_MIN = 0.20           # below this, boxes are noise on farm photos
CONF_CLEAR = 0.45         # above this, a bird a person would not argue about
IOU_NMS = 0.45
CROWD_MIN_BIRDS = 6       # below this, overlap is framing, not occlusion
MAX_PIXELS = 30_000_000   # refuse absurd uploads before decoding

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "yolo11n.onnx")


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    def as_dict(self) -> dict:
        return {
            "x1": round(self.x1, 1), "y1": round(self.y1, 1),
            "x2": round(self.x2, 1), "y2": round(self.y2, 1),
            "confidence": round(self.confidence, 3),
        }


@dataclass(frozen=True)
class CountResult:
    """A count the farmer can check, never a bare number."""

    clear: int            # confident detections
    total: int            # including uncertain ones
    boxes: list[Box]
    width: int
    height: int
    crowding: float       # 0..1, share of detections that overlap another
    note_en: str
    note_hi: str

    @property
    def low(self) -> int:
        return self.clear

    @property
    def high(self) -> int:
        return self.total

    @property
    def best(self) -> int:
        return self.total

    @property
    def quality(self) -> str:
        """How much the farmer should trust this before confirming.

        Two independent signals:

        `spread` — how many detections were uncertain. This is the direct
        measure of the model hedging.

        `crowding` — how packed the birds are, which predicts birds MISSED
        entirely and therefore never appear in either count.

        Crowding alone does not mean a bad count. Three hens filling the frame
        overlap completely and are still counted perfectly. So crowding only
        lowers quality once there are enough birds for occlusion to plausibly
        hide one, which small groups cannot.
        """
        if self.total == 0:
            return "none"
        spread = (self.total - self.clear) / self.total
        occlusion_risk = self.crowding > 0.35 and self.total >= CROWD_MIN_BIRDS

        if spread > 0.5 or occlusion_risk:
            return "low"
        if spread > 0.25 or self.crowding > 0.35:
            return "medium"
        return "high"


def available() -> bool:
    """True when the model and its runtime are both present."""
    if not os.path.exists(MODEL_PATH):
        return False
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    return True


_session = None


def _get_session():
    global _session
    if _session is None:
        import onnxruntime as ort
        _session = ort.InferenceSession(
            MODEL_PATH, providers=["CPUExecutionProvider"]
        )
    return _session


def _letterbox(image, size: int = INPUT_SIZE):
    """Resize preserving aspect ratio, pad to square. Returns the mapping back."""
    from PIL import Image

    w, h = image.size
    ratio = min(size / w, size / h)
    nw, nh = round(w * ratio), round(h * ratio)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    ox, oy = (size - nw) // 2, (size - nh) // 2
    canvas.paste(image.resize((nw, nh), Image.BILINEAR), (ox, oy))
    return canvas, ratio, ox, oy


def _nms(boxes, scores, threshold: float = IOU_NMS):
    """Greedy non-maximum suppression. Keeps the highest-scoring overlaps."""
    import numpy as np

    order = np.argsort(-scores)
    keep = []
    while len(order):
        i = order[0]
        keep.append(int(i))
        if len(order) == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_r - inter + 1e-9)
        order = rest[iou <= threshold]
    return keep


CROWD_IOU = 0.15          # below this, two boxes merely touch at the edges


def _crowding(boxes) -> float:
    """Share of boxes that MEANINGFULLY overlap another box.

    High crowding means birds are packed together, which is exactly when a
    detector misses the ones behind. It is the strongest available signal
    that a count is an undercount.

    The overlap must be a real share of the smaller box, not a single pixel:
    three hens standing apart in a field produce large boxes whose corners
    clip, and counting that as "crowded" made every photo look untrustworthy.
    Intersection-over-smaller is used rather than IoU because a small bird in
    front of a large one is genuine occlusion even though IoU stays low.
    """
    if len(boxes) < 2:
        return 0.0
    import numpy as np

    arr = np.array([[b.x1, b.y1, b.x2, b.y2] for b in boxes], dtype=float)
    areas = np.clip(arr[:, 2] - arr[:, 0], 0, None) * np.clip(
        arr[:, 3] - arr[:, 1], 0, None
    )
    crowded = 0
    for i in range(len(arr)):
        others = np.delete(arr, i, axis=0)
        other_areas = np.delete(areas, i)
        xx1 = np.maximum(arr[i, 0], others[:, 0])
        yy1 = np.maximum(arr[i, 1], others[:, 1])
        xx2 = np.minimum(arr[i, 2], others[:, 2])
        yy2 = np.minimum(arr[i, 3], others[:, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        smaller = np.minimum(areas[i], other_areas)
        overlap = inter / np.maximum(smaller, 1e-9)
        if (overlap > CROWD_IOU).any():
            crowded += 1
    return crowded / len(arr)


def count_birds(image_bytes: bytes) -> CountResult:
    """Detect birds in a photo. Raises ValueError on an unusable image."""
    import io

    import numpy as np
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()                       # cheap structural check
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("That file is not a readable image.") from exc

    width, height = image.size
    if width * height > MAX_PIXELS:
        raise ValueError("That image is too large. Please send a smaller photo.")
    if width < 64 or height < 64:
        raise ValueError("That image is too small to count birds in.")

    canvas, ratio, ox, oy = _letterbox(image)
    tensor = np.asarray(canvas, np.float32).transpose(2, 0, 1)[None] / 255.0

    output = _get_session().run(None, {"images": tensor})[0][0]   # (84, anchors)
    xywh = output[:4].T
    confidence = output[4:].T[:, BIRD_CLASS]

    mask = confidence > CONF_MIN
    boxes: list[Box] = []
    if mask.any():
        raw = xywh[mask]
        scores = confidence[mask]
        corners = np.stack(
            [
                raw[:, 0] - raw[:, 2] / 2, raw[:, 1] - raw[:, 3] / 2,
                raw[:, 0] + raw[:, 2] / 2, raw[:, 1] + raw[:, 3] / 2,
            ],
            axis=1,
        )
        keep = _nms(corners, scores)
        corners, scores = corners[keep], scores[keep]

        # map back to original pixel coordinates
        corners[:, [0, 2]] = (corners[:, [0, 2]] - ox) / ratio
        corners[:, [1, 3]] = (corners[:, [1, 3]] - oy) / ratio
        corners[:, [0, 2]] = np.clip(corners[:, [0, 2]], 0, width)
        corners[:, [1, 3]] = np.clip(corners[:, [1, 3]], 0, height)

        boxes = [
            Box(float(a), float(b), float(c), float(d), float(s))
            for (a, b, c, d), s in zip(corners, scores)
        ]
        boxes.sort(key=lambda b: -b.confidence)

    clear = sum(1 for b in boxes if b.confidence >= CONF_CLEAR)
    crowding = _crowding(boxes)
    note_en, note_hi = _notes(len(boxes), clear, crowding)

    return CountResult(
        clear=clear,
        total=len(boxes),
        boxes=boxes,
        width=width,
        height=height,
        crowding=round(crowding, 3),
        note_en=note_en,
        note_hi=note_hi,
    )


def _notes(total: int, clear: int, crowding: float) -> tuple[str, str]:
    """Say plainly what the number is worth. Never claim certainty."""
    if total == 0:
        return (
            "No birds were found. Try a photo taken from further back in "
            "better light.",
            "कोई पक्षी नहीं मिला। थोड़ा पीछे से, अच्छी रोशनी में फ़ोटो लें।",
        )
    if crowding > 0.35 and total >= CROWD_MIN_BIRDS:
        return (
            "The birds are packed closely, so some behind others were "
            "probably missed. This is likely an undercount — please check "
            "and correct it.",
            "पक्षी पास-पास हैं, इसलिए पीछे वाले छूट सकते हैं। गिनती कम हो सकती "
            "है — कृपया जाँच कर सुधारें।",
        )
    if total > clear:
        return (
            f"{clear} birds are clear; {total - clear} more are uncertain. "
            "Check the boxes and correct the number if needed.",
            f"{clear} पक्षी स्पष्ट हैं; {total - clear} पक्के नहीं। डिब्बे देखकर "
            "संख्या सुधारें।",
        )
    return (
        "All detected birds were clear in this photo. Please still confirm "
        "the number.",
        "इस फ़ोटो में सभी पक्षी स्पष्ट थे। फिर भी संख्या की पुष्टि करें।",
    )
