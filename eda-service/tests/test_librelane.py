from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from toolchain.librelane import PadManifestError, apply_pad_ring, implementation_from_mapping, validate_pad_manifest


def test_classic_is_default_and_does_not_add_pad_variables(tmp_path: Path) -> None:
    config = implementation_from_mapping(None)
    assert config.flow == "Classic"
    assert apply_pad_ring({"DESIGN_NAME": "top"}, config, tmp_path) == {"DESIGN_NAME": "top"}


def test_chip_translation_includes_all_sides_and_cfg(tmp_path: Path) -> None:
    (tmp_path / "pads.cfg").write_text("# real pad config supplied by PDK/design\n")
    (tmp_path / "top.v").write_text("module top; PAD a(); PAD b(); PAD c(); PAD d(); endmodule")
    implementation = implementation_from_mapping({"flow": "Chip", "pad_ring": {"enabled": True, "cfg": "pads.cfg", "south": ["a"], "east": ["b"], "north": ["c"], "west": ["d"]}})
    resolved = apply_pad_ring({"DESIGN_NAME": "top"}, implementation, tmp_path)
    assert resolved["PAD_CFG"] == "pads.cfg"
    assert {key: resolved[key] for key in ("PAD_SOUTH", "PAD_EAST", "PAD_NORTH", "PAD_WEST")} == {"PAD_SOUTH": ["a"], "PAD_EAST": ["b"], "PAD_NORTH": ["c"], "PAD_WEST": ["d"]}


def test_duplicate_pad_is_rejected_deterministically(tmp_path: Path) -> None:
    implementation = implementation_from_mapping({"flow": "Chip", "pad_ring": {"enabled": True, "south": ["p"], "west": ["p"]}})
    with pytest.raises(PadManifestError, match="configured on both south and west"):
        validate_pad_manifest(implementation, tmp_path)


def test_missing_pad_and_cfg_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "top.v").write_text("module top; endmodule")
    implementation = implementation_from_mapping({"flow": "Chip", "pad_ring": {"enabled": True, "cfg": "missing.cfg", "south": ["p"]}})
    with pytest.raises(PadManifestError, match="PAD_CFG does not exist"):
        validate_pad_manifest(implementation, tmp_path)
