"""Golden-gate preview rendering.

This module is the agent service's copy of the eda service's renderer — the
approval gate has to SHOW the golden output long before SIM runs. The two must
infer the same image size from the same dump, or the reviewer approves one
picture and SIM displays another.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memimg import infer_size


def _workspace(tmp_path: Path, marker: str | None) -> Path:
    (tmp_path / "context").mkdir(parents=True, exist_ok=True)
    if marker is not None:
        (tmp_path / "context" / "input_size.txt").write_text(marker)
    return tmp_path


def test_the_size_marker_is_used_when_the_count_fits_it(tmp_path: Path) -> None:
    assert infer_size(_workspace(tmp_path, "32"), 32 * 32, 255) == 32


def test_a_sobel_output_is_not_forced_into_the_input_grid(tmp_path: Path) -> None:
    # 3x3 kernel over 32x32, no padding -> 30x30 = 900 values.
    assert infer_size(_workspace(tmp_path, "32"), 900, 255) == 30


def test_an_rgb_dump_still_matches_the_marker(tmp_path: Path) -> None:
    assert infer_size(_workspace(tmp_path, "16"), 3 * 16 * 16, 255) == 16


def test_without_a_marker_the_count_decides(tmp_path: Path) -> None:
    ws = _workspace(tmp_path, None)
    assert infer_size(ws, 900, 255) == 30
    assert infer_size(ws, 1024, 255) == 32
