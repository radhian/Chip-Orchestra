"""Unit tests for GF180 PDK pad-cell library mapping."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from toolchain.gf180.pad_cells import (
    GF180_PAD_LIBRARY,
    PAD_LIBRARIES,
    PadCellLibrary,
    get_pad_library,
)


class TestGF180PadLibrary:
    def test_library_registered(self) -> None:
        assert "gf180mcuD" in PAD_LIBRARIES
        assert PAD_LIBRARIES["gf180mcuD"] is GF180_PAD_LIBRARY

    def test_pdk_id(self) -> None:
        assert GF180_PAD_LIBRARY.pdk_id == "gf180mcuD"
        assert GF180_PAD_LIBRARY.io_library == "gf180mcu_fd_io"

    def test_input_cells(self) -> None:
        cells = [e.cell_name for e in GF180_PAD_LIBRARY.input]
        assert "gf180mcu_fd_io__in_s" in cells
        assert "gf180mcu_fd_io__in_c" in cells

    def test_bidirectional_cells(self) -> None:
        cells = [e.cell_name for e in GF180_PAD_LIBRARY.bidirectional]
        assert "gf180mcu_fd_io__bi_24t" in cells

    def test_analog_cells(self) -> None:
        cells = [e.cell_name for e in GF180_PAD_LIBRARY.analog]
        assert "gf180mcu_fd_io__asig_5p0" in cells

    def test_power_cells(self) -> None:
        assert GF180_PAD_LIBRARY.default_cell("power") == "gf180mcu_fd_io__dvdd"

    def test_ground_cells(self) -> None:
        assert GF180_PAD_LIBRARY.default_cell("ground") == "gf180mcu_fd_io__dvss"

    def test_corner_cells(self) -> None:
        assert GF180_PAD_LIBRARY.default_cell("corner") == "gf180mcu_fd_io__cor"

    def test_filler_cells(self) -> None:
        fillers = [e.cell_name for e in GF180_PAD_LIBRARY.filler]
        assert len(fillers) == 3
        assert "gf180mcu_fd_io__fill1" in fillers

    def test_all_cells(self) -> None:
        all_cells = GF180_PAD_LIBRARY.all_cells()
        assert "input" in all_cells
        assert "analog" in all_cells
        assert "corner" in all_cells
        # output is empty for GF180 — uses bidirectional instead
        assert "output" not in all_cells

    def test_default_cell_missing_type(self) -> None:
        assert GF180_PAD_LIBRARY.default_cell("output") is None
        assert GF180_PAD_LIBRARY.default_cell("nonexistent") is None


class TestPadLibraryLookup:
    def test_get_known_pdk(self) -> None:
        lib = get_pad_library("gf180mcuD")
        assert lib is GF180_PAD_LIBRARY

    def test_get_unknown_pdk_raises(self) -> None:
        with pytest.raises(KeyError, match="No pad-cell library"):
            get_pad_library("sky130A")

    def test_extensibility(self) -> None:
        """A future PDK can register its own library."""
        test_lib = PadCellLibrary(pdk_id="test_pdk", pdk_name="Test", io_library="test_io")
        PAD_LIBRARIES["test_pdk"] = test_lib
        try:
            assert get_pad_library("test_pdk") is test_lib
        finally:
            del PAD_LIBRARIES["test_pdk"]
