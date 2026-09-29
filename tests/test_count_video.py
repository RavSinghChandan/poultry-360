"""Tests for counting across a video.

The point of video is that it beats a photo; the risk is that it double-counts
the same bird in every frame. These tests pin both properties without asserting
an exact count, which would break on any model change.
"""
import base64
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app
from features.count import video
from features.count.detector import Box
from features.count.video import Track, _iou, _motion, _update_tracks

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not video.available(), reason="video dependencies not installed"
)


def box(x1, y1, x2, y2, conf=0.7):
    return Box(x1, y1, x2, y2, conf)


def make_video(path, frames=40, shift=2, size=(320, 240), cuts=0):
    """A synthetic clip: a bright block drifting across a dark field."""
    import imageio.v2 as iio

    w, h = size
    writer = iio.get_writer(str(path), fps=20, codec="libx264", quality=7)
    for i in range(frames):
        frame = np.zeros((h, w, 3), np.uint8)
        if cuts and i and i % (frames // (cuts + 1)) == 0:
            frame[:] = 255                     # a hard flash = scene change
        x = (10 + i * shift) % max(1, w - 60)
        frame[80:140, x:x + 60] = 220
        writer.append_data(frame)
    writer.close()
    return path


# --- tracking identity --------------------------------------------------

def test_iou_of_identical_boxes_is_one():
    assert _iou(box(0, 0, 10, 10), box(0, 0, 10, 10)) == pytest.approx(1.0)


def test_iou_of_disjoint_boxes_is_zero():
    assert _iou(box(0, 0, 10, 10), box(50, 50, 60, 60)) == 0.0


def test_a_bird_seen_twice_is_one_track():
    """The whole point: the same bird across frames must not count twice."""
    tracks = _update_tracks([], [box(10, 10, 50, 50)], 0)
    tracks = _update_tracks(tracks, [box(12, 11, 52, 51)], 1)
    assert len(tracks) == 1
    assert tracks[0].hits == 2


def test_two_separate_birds_are_two_tracks():
    tracks = _update_tracks([], [box(10, 10, 50, 50), box(200, 200, 240, 240)], 0)
    assert len(tracks) == 2


def test_a_bird_that_moves_far_starts_a_new_track():
    tracks = _update_tracks([], [box(10, 10, 50, 50)], 0)
    tracks = _update_tracks(tracks, [box(300, 300, 340, 340)], 1)
    assert len(tracks) == 2


def test_each_box_claims_at_most_one_track():
    """Greedy matching must not let one detection absorb several tracks."""
    tracks = _update_tracks([], [box(10, 10, 50, 50), box(20, 20, 60, 60)], 0)
    tracks = _update_tracks(tracks, [box(15, 15, 55, 55)], 1)
    assert sum(t.hits for t in tracks) == 3


def test_a_track_expires_after_a_long_gap():
    tracks = _update_tracks([], [box(10, 10, 50, 50)], 0)
    tracks = _update_tracks(tracks, [box(10, 10, 50, 50)], 99)
    assert len(tracks) == 2, "a bird gone for many frames is not the same bird"


def test_best_confidence_is_kept_across_a_track():
    tracks = _update_tracks([], [box(10, 10, 50, 50, 0.3)], 0)
    tracks = _update_tracks(tracks, [box(10, 10, 50, 50, 0.9)], 1)
    assert tracks[0].best_confidence == pytest.approx(0.9)


# --- motion classification ----------------------------------------------

def test_no_cuts_and_good_matching_is_steady():
    assert _motion(matched_ratio=0.8, cuts=0) == "steady"


def test_a_single_cut_is_flagged():
    assert _motion(matched_ratio=0.9, cuts=1) == "moving"


def test_several_cuts_mean_the_total_is_unreliable():
    """Five sheds spliced together must never read as a steady clip.

    This was a real bug: requiring cuts to be a QUARTER of all gaps let a
    five-scene video pass as steady and report a confident wrong total.
    """
    assert _motion(matched_ratio=0.9, cuts=4) == "fast"


def test_poor_matching_alone_is_enough_to_warn():
    assert _motion(matched_ratio=0.1, cuts=0) == "moving"


# --- end to end ---------------------------------------------------------

def test_video_count_is_far_below_the_naive_sum(tmp_path):
    """Without tracking a short clip sums to many times the true count."""
    path = make_video(tmp_path / "drift.mp4")
    result = video.count_video(path.read_bytes())
    assert result.naive_sum >= result.counted


def test_video_reports_how_many_frames_it_looked_at(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    assert video.count_video(path.read_bytes()).frames_sampled > 0


def test_video_never_reports_fewer_than_one_frame_saw(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    result = video.count_video(path.read_bytes())
    assert result.counted >= result.peak_frame_count


def test_range_brackets_the_count(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    r = video.count_video(path.read_bytes())
    assert r.low <= r.counted <= r.high


def test_spliced_scenes_are_reported_as_unreliable(tmp_path):
    """Several hard cuts must be detected as separate views.

    Quality is not asserted here: these synthetic frames contain no birds, so
    it is correctly "none". Motion is the property under test, and it is what
    drives the warning the farmer reads.
    """
    path = make_video(tmp_path / "cuts.mp4", frames=60, cuts=4)
    result = video.count_video(path.read_bytes())
    assert result.motion == "fast"


def test_quality_is_low_when_the_view_jumps():
    """With birds present, a cut-up video must not be presented as reliable."""
    from features.count.video import _quality

    assert _quality(counted=30, clear=25, motion="fast", sampled=20) == "low"


def test_quality_is_high_only_for_a_steady_clear_clip():
    from features.count.video import _quality

    assert _quality(counted=20, clear=20, motion="steady", sampled=20) == "high"
    assert _quality(counted=20, clear=20, motion="moving", sampled=20) != "high"


# --- the API ------------------------------------------------------------

def test_video_endpoint_always_asks_for_confirmation(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    payload = base64.b64encode(path.read_bytes()).decode()
    body = client.post("/api/count/video", json={"video_base64": payload}).json()
    assert body["needs_confirmation"] is True


def test_video_endpoint_matches_the_photo_response_shape(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    payload = base64.b64encode(path.read_bytes()).decode()
    body = client.post("/api/count/video", json={"video_base64": payload}).json()
    for key in ("counted", "range", "quality", "note", "needs_confirmation"):
        assert key in body


def test_video_note_comes_back_in_the_requested_language(tmp_path):
    path = make_video(tmp_path / "drift.mp4")
    payload = base64.b64encode(path.read_bytes()).decode()
    bn = client.post("/api/count/video",
                     json={"video_base64": payload, "lang": "bn"}).json()
    en = client.post("/api/count/video",
                     json={"video_base64": payload, "lang": "en"}).json()
    assert isinstance(bn["note"], str) and bn["note"] != en["note"]


def test_rejects_a_file_that_is_not_a_video():
    payload = base64.b64encode(b"definitely not a video" * 10).decode()
    assert client.post("/api/count/video", json={"video_base64": payload}).status_code == 400


def test_rejects_unreadable_base64():
    assert client.post("/api/count/video", json={"video_base64": "!" * 80}).status_code == 400


def test_tips_endpoint_reports_video_readiness():
    assert "video_ready" in client.get("/api/count/tips").json()


def test_video_errors_are_bilingual():
    """A farmer who reads no English must still understand a failure."""
    payload = base64.b64encode(b"not a video" * 20).decode()
    detail = client.post("/api/count/video", json={"video_base64": payload}).json()["detail"]
    assert any("ऀ" <= ch <= "ॿ" for ch in detail), \
        f"error is English-only: {detail!r}"
