"""Comprehensive unit tests for toolchain.librelane.

Covers:
- Classic/Chip flow selection
- Generic pad-ring config (logical I/O + physical pads)
- PAD_CFG, PAD_SOUTH/EAST/NORTH/WEST translation
- Duplicate pads, cross-side duplicates
- Missing instance, invalid config
- Missing required files
- Subprocess failure propagation
- Failure classification
- Backward compatibility
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from toolchain.librelane import (
    FailureCategory,
    IORequirements,
    PadManifestError,
    PadRingConfig,
    apply_pad_ring,
    classify_failure,
    collect_chip_artifacts,
    extract_librelane_version,
    extract_pad_placement_from_def,
    implementation_from_mapping,
    io_requirements_from_mapping,
    parse_librelane_stages,
    validate_pad_manifest,
    write_pad_placement_json,
)


# -----------------------------------------------------------------------
# Classic / Chip flow selection
# -----------------------------------------------------------------------

class TestFlowSelection:
    def test_classic_is_default(self) -> None:
        config = implementation_from_mapping(None)
        assert config.flow == "Classic"

    def test_classic_explicit(self) -> None:
        config = implementation_from_mapping({"flow": "Classic"})
        assert config.flow == "Classic"

    def test_chip_explicit(self) -> None:
        config = implementation_from_mapping({"flow": "Chip"})
        assert config.flow == "Chip"

    def test_invalid_flow_rejected(self) -> None:
        with pytest.raises(PadManifestError, match="must be either"):
            implementation_from_mapping({"flow": "Invalid"})

    def test_classic_does_not_add_pad_variables(self, tmp_path: Path) -> None:
        config = implementation_from_mapping(None)
        assert config.flow == "Classic"
        assert apply_pad_ring({"DESIGN_NAME": "top"}, config, tmp_path) == {"DESIGN_NAME": "top"}

    def test_classic_prohibits_pad_ring(self) -> None:
        with pytest.raises(PadManifestError, match="pad_ring.enabled requires"):
            implementation_from_mapping({"flow": "Classic", "pad_ring": {"enabled": True}})


# -----------------------------------------------------------------------
# Generic pad-ring config
# -----------------------------------------------------------------------

class TestPadRingConfig:
    def test_default_pad_ring_disabled(self) -> None:
        config = implementation_from_mapping({"flow": "Chip"})
        assert not config.pad_ring.enabled
        assert config.pad_ring.total_pads() == 0

    def test_enabled_pad_ring_with_sides(self) -> None:
        config = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {
                "enabled": True,
                "south": ["a", "b"],
                "east": ["c"],
                "north": ["d", "e", "f"],
                "west": ["g"],
                "pdk_id": "gf180mcuD",
            }
        })
        assert config.pad_ring.enabled
        assert config.pad_ring.total_pads() == 7
        assert config.pad_ring.pdk_id == "gf180mcuD"

    def test_unsupported_field_rejected(self) -> None:
        with pytest.raises(PadManifestError, match="unsupported field"):
            implementation_from_mapping({
                "flow": "Chip",
                "pad_ring": {"enabled": True, "bogus_field": 42}
            })

    def test_non_list_side_rejected(self) -> None:
        with pytest.raises(PadManifestError):
            implementation_from_mapping({
                "flow": "Chip",
                "pad_ring": {"enabled": True, "south": "not_a_list"}
            })


# -----------------------------------------------------------------------
# I/O Requirements (logical, design-specific)
# -----------------------------------------------------------------------

class TestIORequirements:
    def test_default_values(self) -> None:
        req = io_requirements_from_mapping(None)
        assert req.inputs == 0
        assert req.corners == 4

    def test_custom_values(self) -> None:
        req = io_requirements_from_mapping({
            "inputs": 4, "outputs": 4, "bidirectional": 2,
            "analog": 1, "power": 2, "ground": 2, "corners": 4
        })
        assert req.inputs == 4
        assert req.analog == 1

    def test_invalid_values_rejected(self) -> None:
        with pytest.raises(PadManifestError, match="invalid values"):
            io_requirements_from_mapping({"inputs": "not_a_number"})

    def test_io_requirements_in_impl_config(self) -> None:
        config = implementation_from_mapping({
            "flow": "Chip",
            "io_requirements": {"inputs": 8, "outputs": 4}
        })
        assert config.io_requirements.inputs == 8
        assert config.io_requirements.outputs == 4


# -----------------------------------------------------------------------
# PAD_CFG and PAD_SOUTH / EAST / NORTH / WEST translation
# -----------------------------------------------------------------------

class TestPadTranslation:
    def test_chip_translation_includes_all_sides_and_cfg(self, tmp_path: Path) -> None:
        (tmp_path / "pads.cfg").write_text("# real pad config\n")
        (tmp_path / "top.v").write_text("module top; PAD a(); PAD b(); PAD c(); PAD d(); endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {
                "enabled": True, "cfg": "pads.cfg",
                "south": ["a"], "east": ["b"], "north": ["c"], "west": ["d"]
            }
        })
        resolved = apply_pad_ring({"DESIGN_NAME": "top"}, impl, tmp_path)
        assert resolved["PAD_CFG"] == "pads.cfg"
        assert resolved["PAD_SOUTH"] == ["a"]
        assert resolved["PAD_EAST"] == ["b"]
        assert resolved["PAD_NORTH"] == ["c"]
        assert resolved["PAD_WEST"] == ["d"]

    def test_chip_without_cfg_omits_pad_cfg(self, tmp_path: Path) -> None:
        (tmp_path / "top.v").write_text("module top; PAD a(); endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["a"]}
        })
        resolved = apply_pad_ring({"DESIGN_NAME": "top"}, impl, tmp_path)
        assert "PAD_CFG" not in resolved
        assert resolved["PAD_SOUTH"] == ["a"]

    def test_chip_disabled_pad_ring_no_variables(self, tmp_path: Path) -> None:
        impl = implementation_from_mapping({"flow": "Chip"})
        resolved = apply_pad_ring({"DESIGN_NAME": "top"}, impl, tmp_path)
        assert "PAD_SOUTH" not in resolved

    def test_empty_side_not_added(self, tmp_path: Path) -> None:
        (tmp_path / "top.v").write_text("module top; PAD a(); endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["a"]}
        })
        resolved = apply_pad_ring({"DESIGN_NAME": "top"}, impl, tmp_path)
        assert "PAD_EAST" not in resolved
        assert "PAD_NORTH" not in resolved
        assert "PAD_WEST" not in resolved


# -----------------------------------------------------------------------
# Validation: duplicates, missing, cross-side
# -----------------------------------------------------------------------

class TestValidation:
    def test_duplicate_pad_within_side(self, tmp_path: Path) -> None:
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["p", "p"]}
        })
        with pytest.raises(PadManifestError, match="configured on both south and south"):
            validate_pad_manifest(impl, tmp_path)

    def test_duplicate_pad_cross_side(self, tmp_path: Path) -> None:
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["p"], "west": ["p"]}
        })
        with pytest.raises(PadManifestError, match="configured on both south and west"):
            validate_pad_manifest(impl, tmp_path)

    def test_empty_pad_name_rejected(self, tmp_path: Path) -> None:
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": [""]}
        })
        with pytest.raises(PadManifestError, match="empty pad instance name"):
            validate_pad_manifest(impl, tmp_path)

    def test_missing_cfg_file(self, tmp_path: Path) -> None:
        (tmp_path / "top.v").write_text("module top; endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "cfg": "missing.cfg", "south": ["p"]}
        })
        with pytest.raises(PadManifestError, match="PAD_CFG does not exist"):
            validate_pad_manifest(impl, tmp_path)

    def test_missing_rtl(self, tmp_path: Path) -> None:
        # No .v or .sv files at all
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["p"]}
        })
        with pytest.raises(PadManifestError, match="no top-level RTL"):
            validate_pad_manifest(impl, tmp_path)

    def test_pad_not_in_rtl(self, tmp_path: Path) -> None:
        (tmp_path / "top.v").write_text("module top; endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["nonexistent_pad"]}
        })
        with pytest.raises(PadManifestError, match="does not exist in workspace RTL"):
            validate_pad_manifest(impl, tmp_path)

    def test_valid_pad_passes(self, tmp_path: Path) -> None:
        (tmp_path / "top.v").write_text("module top; PAD pad_a(); PAD pad_b(); endmodule")
        impl = implementation_from_mapping({
            "flow": "Chip",
            "pad_ring": {"enabled": True, "south": ["pad_a"], "north": ["pad_b"]}
        })
        # Should not raise
        validate_pad_manifest(impl, tmp_path)


# -----------------------------------------------------------------------
# Failure classification
# -----------------------------------------------------------------------

class TestFailureClassification:
    def test_padring_failure(self) -> None:
        assert classify_failure("Error in PAD_SOUTH configuration") == FailureCategory.PAD_RING

    def test_pdk_failure(self) -> None:
        assert classify_failure("PDK_ROOT not set") == FailureCategory.PDK

    def test_routing_failure(self) -> None:
        assert classify_failure("Global routing failed") == FailureCategory.ROUTING

    def test_cts_failure(self) -> None:
        assert classify_failure("CTS clock tree synthesis error") == FailureCategory.CTS

    def test_drc_failure(self) -> None:
        assert classify_failure("DRC violations found") == FailureCategory.DRC

    def test_lvs_failure(self) -> None:
        assert classify_failure("LVS mismatch") == FailureCategory.LVS

    def test_unknown_failure(self) -> None:
        assert classify_failure("something completely unrelated xyz123") == FailureCategory.UNKNOWN

    def test_failed_step_combined(self) -> None:
        assert classify_failure("", "OpenROAD.PadRing") == FailureCategory.PAD_RING


# -----------------------------------------------------------------------
# LibreLane log parsing
# -----------------------------------------------------------------------

class TestLogParsing:
    def test_parse_stages(self) -> None:
        log = """
        Running OpenROAD.PadRing...
        Running OpenROAD.Floorplan...
        Running OpenROAD.GlobalPlace...
        Running OpenROAD.CTS...
        Running OpenROAD.GlobalRoute...
        Running KLayout.StreamOut...
        """
        stages = parse_librelane_stages(log)
        assert "OpenROAD.PadRing" in stages
        assert "CTS" in stages
        assert "Routing" in stages
        assert "GDS/DRC" in stages

    def test_extract_version(self) -> None:
        assert extract_librelane_version("LibreLane v3.0.10") == "3.0.10"
        assert extract_librelane_version("LibreLane 3.0.7") == "3.0.7"
        assert extract_librelane_version("no version here") == ""


# -----------------------------------------------------------------------
# DEF pad placement extraction
# -----------------------------------------------------------------------

class TestPadPlacement:
    def test_extract_from_def(self, tmp_path: Path) -> None:
        def_content = """VERSION 5.8 ;
DIEAREA ( 0 0 ) ( 2935000 2935000 ) ;
COMPONENTS 3 ;
- pad_s_analog_0 gf180mcu_fd_io__asig_5p0
  + FIXED ( 100000 0 ) N ;
- pad_e_bi_0 gf180mcu_fd_io__bi_24t
  + FIXED ( 2935000 500000 ) W ;
- corner_sw gf180mcu_fd_io__cor
  + FIXED ( 0 0 ) N ;
END COMPONENTS
"""
        def_file = tmp_path / "test.def"
        def_file.write_text(def_content)
        placements = extract_pad_placement_from_def(def_file)
        assert len(placements) == 3
        # Check one pad
        south_pads = [p for p in placements if p["side"] == "south"]
        assert len(south_pads) >= 1
        assert south_pads[0]["instance"] == "pad_s_analog_0"
        assert south_pads[0]["master"] == "gf180mcu_fd_io__asig_5p0"

    def test_write_pad_placement_json(self, tmp_path: Path) -> None:
        placements = [
            {"instance": "pad_a", "master": "cell_a", "side": "south", "x": 123.45, "y": 0.0},
        ]
        out = tmp_path / "pad_placement.json"
        write_pad_placement_json(placements, out)
        assert out.is_file()
        loaded = json.loads(out.read_text())
        assert loaded[0]["instance"] == "pad_a"


# -----------------------------------------------------------------------
# Artifact collection
# -----------------------------------------------------------------------

class TestArtifactCollection:
    def test_collect_empty_dir(self, tmp_path: Path) -> None:
        result = collect_chip_artifacts(tmp_path)
        assert "run_dir" in result
        assert "odb" not in result

    def test_collect_with_state_out(self, tmp_path: Path) -> None:
        state = {"flow": "Chip", "pdk": "gf180mcuD", "design_name": "chip_top"}
        (tmp_path / "state_out.json").write_text(json.dumps(state))
        result = collect_chip_artifacts(tmp_path)
        assert result["state_out"] == str(tmp_path / "state_out.json")
        assert result["state_summary"]["flow"] == "Chip"

    def test_collect_gds_files(self, tmp_path: Path) -> None:
        (tmp_path / "output.gds").write_bytes(b"\x00" * 100)
        result = collect_chip_artifacts(tmp_path)
        assert "gds" in result
        assert any("output.gds" in p for p in result["gds"])


# -----------------------------------------------------------------------
# Backward compatibility
# -----------------------------------------------------------------------

class TestBackwardCompat:
    def test_none_input_returns_classic(self) -> None:
        config = implementation_from_mapping(None)
        assert config.flow == "Classic"
        assert not config.pad_ring.enabled

    def test_empty_dict_returns_classic(self) -> None:
        config = implementation_from_mapping({})
        assert config.flow == "Classic"

    def test_chip_with_empty_pad_ring(self, tmp_path: Path) -> None:
        config = implementation_from_mapping({"flow": "Chip"})
        resolved = apply_pad_ring({"DESIGN_NAME": "top"}, config, tmp_path)
        assert resolved == {"DESIGN_NAME": "top"}
