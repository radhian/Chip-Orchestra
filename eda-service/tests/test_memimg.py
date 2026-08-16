"""Rendering a .mem dump to a preview PNG.

The size marker (``context/input_size.txt``) describes the chip's INPUT grid.
Output dumps are a different shape whenever the kernel shrinks the frame, and
rendering one at the input's size silently shears the image instead of failing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolchain.memimg import infer_size


def _workspace(tmp_path: Path, marker: str | None) -> Path:
    (tmp_path / "context").mkdir(parents=True, exist_ok=True)
    if marker is not None:
        (tmp_path / "context" / "input_size.txt").write_text(marker)
    return tmp_path


def test_the_size_marker_is_used_when_the_count_fits_it(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "32")
    assert infer_size(ws, 32 * 32, 255) == 32


def test_a_sobel_output_is_not_forced_into_the_input_grid(tmp_path: Path) -> None:
    # 3x3 kernel over 32x32, no padding -> 30x30 = 900 values. Rendering those
    # at 32 wide shifts every row 2px further left: the edge map came out as a
    # diagonal smear that matched neither the golden model nor the chip.
    ws = _workspace(tmp_path, "32")
    assert infer_size(ws, 900, 255) == 30


def test_an_rgb_dump_still_matches_the_marker(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "16")
    assert infer_size(ws, 3 * 16 * 16, 255) == 16


def test_without_a_marker_the_count_decides(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, None)
    assert infer_size(ws, 900, 255) == 30
    assert infer_size(ws, 1024, 255) == 32


def test_a_garbage_marker_does_not_break_inference(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, "not-a-number")
    assert infer_size(ws, 900, 255) == 30


# --------------------------------------------------------------------------- #
# Clock resolution across the API boundary. Nothing populates a clock target
# from the spec, so a design's own declared frequency has to survive the trip.
# --------------------------------------------------------------------------- #
def test_an_unspecified_clock_stays_unspecified_across_the_api() -> None:
    """main.py used to substitute 10 ns here, which hid the caller's silence
    from the job runner and hardened a 50 MHz design at 100 MHz."""
    from main import CreateEDAJobRequest

    req = CreateEDAJobRequest(task_id="t", stage="SYNTH")
    assert req.build_options()["clock_period"] == 0.0


def test_an_explicit_clock_still_wins() -> None:
    from main import CreateEDAJobRequest

    req = CreateEDAJobRequest(task_id="t", stage="SYNTH", clock_period=12.5)
    assert req.build_options()["clock_period"] == 12.5
