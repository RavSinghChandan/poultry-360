"""Count birds across a short video instead of a single photo.

WHY VIDEO HELPS
---------------
A bird hidden behind another in frame 1 is often visible in frame 40. Several
views of the same shed genuinely recover birds a single photo cannot see.

WHY VIDEO IS ALSO HARDER
------------------------
Counting each frame and adding them up is catastrophically wrong: a 3-second
pan over ~25 birds sums to 100, because the same bird is counted in every
frame it appears in. The real work is deciding which detections across frames
are the SAME bird.

HOW IDENTITY IS DECIDED
-----------------------
Detections in consecutive sampled frames are matched greedily by box overlap
(IoU). A matched detection continues an existing track; an unmatched one
starts a new track. The count is the number of tracks that were seen in
enough frames to be believed.

This is deliberately simple. It assumes the camera moves slowly and birds do
not teleport, which is true of a farmer walking a phone across a shed and
false of a fast whip-pan. `advice` says which case the video looked like.

WHAT IT STILL CANNOT DO
-----------------------
It cannot give an exact count. A bird that never becomes visible in any frame
is invisible to every frame. A bird that leaves and re-enters the frame is
counted twice. Panning across a large shed can show disjoint groups that
tracking has no way to relate. So this returns a range and a quality flag,
and the farmer's confirmation remains what gets recorded.
"""
from __future__ import annotations

import io
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

from .detector import CONF_CLEAR, CONF_MIN, Box, count_birds

MAX_VIDEO_BYTES = 80 * 1024 * 1024
MAX_DURATION_S = 75.0            # a farmer's clip, not a security recording
TARGET_SAMPLES = 24              # frames actually run through the detector
MIN_TRACK_HITS = 2               # a track seen once may be a flicker
TRACK_IOU = 0.30                 # overlap needed to call it the same bird
MAX_GAP_FRAMES = 2               # sampled frames a track may vanish for


@dataclass
class Track:
    """One bird, followed across sampled frames."""

    box: Box
    hits: int = 1
    best_confidence: float = 0.0
    last_seen: int = 0
    frames: list[int] = field(default_factory=list)

    @property
    def clear(self) -> bool:
        return self.best_confidence >= CONF_CLEAR


@dataclass(frozen=True)
class VideoResult:
    counted: int
    low: int
    high: int
    clear: int
    tracks: int
    frames_sampled: int
    duration_s: float
    peak_frame_count: int
    naive_sum: int                # what summing frames would have said
    motion: str                   # "steady" | "moving" | "fast"
    note_en: str
    note_hi: str
    quality: str


def available() -> bool:
    try:
        import imageio_ffmpeg  # noqa: F401

        from .detector import available as det_available
        return det_available()
    except ImportError:
        return False


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _probe_duration(path: str) -> float:
    """Duration in seconds, via ffmpeg's own stderr. Zero if unknown."""
    proc = subprocess.run(
        [_ffmpeg(), "-i", path], capture_output=True, text=True, timeout=30
    )
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = stamp.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                return 0.0
    return 0.0


def _iou(a: Box, b: Box) -> float:
    x1, y1 = max(a.x1, b.x1), max(a.y1, b.y1)
    x2, y2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter <= 0:
        return 0.0
    area_a = (a.x2 - a.x1) * (a.y2 - a.y1)
    area_b = (b.x2 - b.x1) * (b.y2 - b.y1)
    return inter / (area_a + area_b - inter + 1e-9)


def _update_tracks(tracks: list[Track], boxes: list[Box], index: int) -> list[Track]:
    """Greedy IoU matching: strongest overlaps claim their track first."""
    pairs = []
    for bi, box in enumerate(boxes):
        for ti, track in enumerate(tracks):
            if index - track.last_seen > MAX_GAP_FRAMES:
                continue
            score = _iou(box, track.box)
            if score >= TRACK_IOU:
                pairs.append((score, bi, ti))
    pairs.sort(reverse=True)

    used_boxes: set[int] = set()
    used_tracks: set[int] = set()
    for score, bi, ti in pairs:
        if bi in used_boxes or ti in used_tracks:
            continue
        track = tracks[ti]
        track.box = boxes[bi]
        track.hits += 1
        track.best_confidence = max(track.best_confidence, boxes[bi].confidence)
        track.last_seen = index
        track.frames.append(index)
        used_boxes.add(bi)
        used_tracks.add(ti)

    for bi, box in enumerate(boxes):
        if bi in used_boxes:
            continue
        tracks.append(
            Track(box=box, best_confidence=box.confidence, last_seen=index,
                  frames=[index])
        )
    return tracks


def _frame_signature(frame) -> "object":
    """A tiny greyscale thumbnail, used to tell whether the view jumped.

    Track bookkeeping alone cannot detect a hard cut: within each shot the
    tracker matches perfectly, so the matched ratio stays high even when the
    video is five unrelated scenes spliced together. Comparing the frames
    themselves is the only reliable signal.
    """
    import numpy as np
    from PIL import Image

    small = Image.fromarray(frame).convert("L").resize((32, 32), Image.BILINEAR)
    return np.asarray(small, dtype=np.float32) / 255.0


def _scene_change(a, b) -> float:
    """0 = identical view, 1 = completely unrelated."""
    import numpy as np

    return float(np.abs(a - b).mean())


SCENE_CUT = 0.18          # above this, the view jumped rather than drifted


def _motion(matched_ratio: float, cuts: int) -> str:
    """How much the view changed between samples.

    `cuts` counts sample gaps where the picture jumped rather than drifted.
    Even ONE cut means the video contains views with no bird in common, so
    tracking cannot tell whether the birds after the cut are the birds before
    it. Two or more cuts means the clip is really several separate scenes and
    the total is close to meaningless — a sum of unrelated groups.

    An earlier version required a quarter of all gaps to be cuts before
    complaining. A video of five different sheds spliced together has only
    four cuts in thirty gaps, so it passed as "steady" and reported a
    confidently wrong total. Counting cuts rather than their share fixes that.
    """
    if cuts >= 2:
        return "fast"
    if cuts == 1 or matched_ratio < 0.55:
        return "moving"
    return "steady"


def count_video(video_bytes: bytes) -> VideoResult:
    """Decode, sample, detect and track. Raises ValueError on a bad video."""
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise ValueError("That video is too large. Please send a shorter clip.")

    import imageio.v2 as iio
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        path = tmp.name

    try:
        duration = _probe_duration(path)
        if duration > MAX_DURATION_S:
            raise ValueError(
                f"That video is {duration:.0f} seconds. "
                f"Please send one under {int(MAX_DURATION_S)} seconds."
            )
        try:
            reader = iio.get_reader(path)
        except Exception as exc:
            raise ValueError("That file could not be read as a video.") from exc

        try:
            total = reader.count_frames()
        except Exception:
            total = 0
        if not total or total < 2:
            raise ValueError("That video has too few frames to count.")

        step = max(1, total // TARGET_SAMPLES)
        wanted = set(range(0, total, step))

        tracks: list[Track] = []
        per_frame: list[int] = []
        naive = 0
        matched_events = 0
        detection_events = 0
        sampled = 0
        previous_signature = None
        cuts = 0
        gaps = 0

        for index, frame in enumerate(reader):
            if index not in wanted:
                continue
            signature = _frame_signature(frame)
            cut_here = False
            if previous_signature is not None:
                gaps += 1
                if _scene_change(previous_signature, signature) > SCENE_CUT:
                    cuts += 1
                    cut_here = True
            previous_signature = signature

            buffer = io.BytesIO()
            Image.fromarray(frame).save(buffer, format="JPEG", quality=88)
            try:
                result = count_birds(buffer.getvalue())
            except ValueError:
                continue

            # After a cut nothing on screen is the same bird, so no track may
            # continue across it. Expiring them prevents a silent mismatch.
            if cut_here:
                for track in tracks:
                    track.last_seen = -999

            before = len(tracks)
            tracks = _update_tracks(tracks, result.boxes, sampled)
            new_tracks = len(tracks) - before
            detection_events += len(result.boxes)
            matched_events += max(0, len(result.boxes) - new_tracks)

            per_frame.append(result.total)
            naive += result.total
            sampled += 1

        reader.close()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if not per_frame:
        raise ValueError("No frames in that video could be read.")

    believed = [t for t in tracks if t.hits >= MIN_TRACK_HITS]
    clear = sum(1 for t in believed if t.clear)
    peak = max(per_frame)
    counted = max(len(believed), peak)      # never report fewer than one frame saw

    ratio = matched_events / detection_events if detection_events else 0.0
    motion = _motion(ratio, cuts)
    quality = _quality(counted, clear, motion, sampled)
    note_en, note_hi = _notes(counted, clear, peak, motion, quality)

    return VideoResult(
        counted=counted,
        low=max(peak, clear),
        high=max(counted, len(tracks)),
        clear=clear,
        tracks=len(tracks),
        frames_sampled=sampled,
        duration_s=round(duration, 1),
        peak_frame_count=peak,
        naive_sum=naive,
        motion=motion,
        note_en=note_en,
        note_hi=note_hi,
        quality=quality,
    )


def _quality(counted: int, clear: int, motion: str, sampled: int) -> str:
    if counted == 0:
        return "none"
    if motion == "fast" or sampled < 4:
        return "low"
    spread = (counted - clear) / max(counted, 1)
    if motion == "moving" or spread > 0.5:
        return "medium" if motion != "fast" else "low"
    if spread > 0.25:
        return "medium"
    return "high"


def _notes(counted, clear, peak, motion, quality) -> tuple[str, str]:
    if counted == 0:
        return (
            "No birds were found in this video. Try filming in better light, "
            "moving the phone slowly.",
            "इस वीडियो में कोई पक्षी नहीं मिला। बेहतर रोशनी में, फ़ोन धीरे-धीरे "
            "घुमाकर वीडियो लें।",
        )
    if motion == "fast":
        return (
            "This video jumps between separate views, so birds cannot be "
            "followed across it and this total is not reliable. Film one "
            "continuous clip, walking slowly, and count one shed at a time.",
            "यह वीडियो अलग-अलग दृश्यों में कूदता है, इसलिए पक्षियों का पीछा नहीं "
            "किया जा सकता और यह संख्या भरोसेमंद नहीं है। एक ही बार में, धीरे "
            "चलकर, एक शेड का वीडियो लें।",
        )
    if counted > peak:
        return (
            f"{counted} birds were followed across the video; the busiest "
            f"single frame showed {peak}. Moving the camera found birds a "
            "photo would have missed. Please confirm the number.",
            f"वीडियो में {counted} पक्षी गिने गए; एक फ़्रेम में सबसे ज़्यादा "
            f"{peak} दिखे। कैमरा घुमाने से वे पक्षी मिले जो फ़ोटो में छूट जाते। "
            "कृपया संख्या की पुष्टि करें।",
        )
    return (
        f"{counted} birds were followed across the video. Please confirm "
        "the number.",
        f"वीडियो में {counted} पक्षी गिने गए। कृपया संख्या की पुष्टि करें।",
    )
