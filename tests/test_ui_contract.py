"""The UI's structural contract.

These are not screenshot tests. They assert the properties that, when wrong,
make the app look broken to a farmer holding a phone — and every one of them
corresponds to a bug that actually shipped.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "frontend/src/app/features/count/count.component.ts"
ROUTES = ROOT / "frontend/src/app/app.routes.ts"

pytestmark = pytest.mark.skipif(
    not COMPONENT.exists(), reason="frontend sources not present"
)


def component() -> str:
    return COMPONENT.read_text()


def test_upload_controls_are_real_buttons():
    """A <label> wrapping a hidden input is unreliable on mobile Safari.

    Buttons that call input.click() work everywhere.
    """
    assert 'type="button" class="pick"' in component()


def test_file_inputs_are_driven_by_template_refs():
    src = component()
    assert "#photoInput" in src and "#videoInput" in src
    assert "photoInput.click()" in src and "videoInput.click()" in src


def test_capture_is_not_forced():
    """`capture` makes iOS open the camera with no way to pick an existing file."""
    assert "capture=" not in component(), \
        "capture attribute blocks choosing a photo from the gallery"


def test_both_photo_and_video_are_offered():
    src = component()
    assert 'accept="image/*"' in src
    assert 'accept="video/*"' in src


def test_the_file_input_is_cleared_after_selection():
    """Without this, picking the same file twice fires no change event."""
    assert "input.value = ''" in component()


def test_a_spinner_is_shown_while_working():
    """A 20-second wait with no feedback reads as a dead button."""
    src = component()
    assert 'class="working"' in src and 'class="spinner"' in src


def test_buttons_are_disabled_while_busy():
    assert '[disabled]="busy()"' in component()


def test_tap_targets_are_large_enough():
    """Anything under ~48px is hard to hit accurately on a phone."""
    match = re.search(r"\.pick\{[^}]*min-height:(\d+)px", component())
    assert match and int(match.group(1)) >= 48


def test_the_app_opens_on_the_count_screen():
    src = ROUTES.read_text()
    assert "redirectTo: 'count'" in src, "landing on another feature hides this one"


def test_template_literal_is_balanced():
    """A stray backtick inside the template silently breaks the build."""
    assert component().count("`") % 2 == 0


# --- reachable from a phone ---------------------------------------------

RUN_SH = ROOT / "run.sh"


def test_the_server_binds_to_every_interface():
    """On 127.0.0.1 the app is invisible to every phone on the Wi-Fi.

    This shipped: run.sh bound to loopback, so the app worked at the desk and
    was unreachable from the shed, which is where it is actually used.
    """
    src = RUN_SH.read_text()
    assert "--host 127.0.0.1" not in src, "loopback binding blocks all phones"
    assert "0.0.0.0" in src


def test_startup_prints_the_phone_address():
    """Nobody should have to ask what URL to type on their phone."""
    assert "On a phone" in RUN_SH.read_text()
