"""GF180MCU PDK pad-cell library mapping.

Provides a PDK-aware mapping from *logical* pad types (input, output,
bidirectional, analog, power, ground, corner) to the actual GF180 I/O library
cells.  Future PDKs implement the same ``PadCellLibrary`` interface with their
own cell names.

The mapping is intentionally explicit: every cell referenced here must exist in
the installed GF180 PDK.  Generic Chip Orchestra logic never hard-codes cell
names — it always looks them up through this layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PadCellEntry:
    """One physical pad-cell type the PDK provides."""
    cell_name: str
    description: str = ""
    # The I/O library it belongs to (used for LEF/lib lookups).
    library: str = ""


@dataclass(frozen=True)
class PadCellLibrary:
    """Maps logical pad roles to physical PDK cells.

    Every PDK that Chip Orchestra supports must provide one of these.  The
    ``pdk_id`` is the key used throughout the system to select the mapping.
    """
    pdk_id: str
    pdk_name: str
    io_library: str

    # Logical-type → cell mapping.  A type may offer multiple variants; the
    # first entry is the default.
    input: List[PadCellEntry] = field(default_factory=list)
    output: List[PadCellEntry] = field(default_factory=list)
    bidirectional: List[PadCellEntry] = field(default_factory=list)
    analog: List[PadCellEntry] = field(default_factory=list)
    power: List[PadCellEntry] = field(default_factory=list)
    ground: List[PadCellEntry] = field(default_factory=list)
    corner: List[PadCellEntry] = field(default_factory=list)
    filler: List[PadCellEntry] = field(default_factory=list)

    def default_cell(self, logical_type: str) -> Optional[str]:
        """Return the default cell name for a logical pad type, or None."""
        entries: List[PadCellEntry] = getattr(self, logical_type, [])
        return entries[0].cell_name if entries else None

    def all_cells(self) -> Dict[str, List[str]]:
        """Return {logical_type: [cell_name, ...]} for every populated type."""
        result: Dict[str, List[str]] = {}
        for role in ("input", "output", "bidirectional", "analog",
                     "power", "ground", "corner", "filler"):
            entries: List[PadCellEntry] = getattr(self, role, [])
            if entries:
                result[role] = [e.cell_name for e in entries]
        return result


# ---------------------------------------------------------------------------
# GF180MCU pad-cell library (real cells from gf180mcu_fd_io / gf180mcu_ws_io)
# ---------------------------------------------------------------------------

GF180_PAD_LIBRARY = PadCellLibrary(
    pdk_id="gf180mcuD",
    pdk_name="GlobalFoundries 180nm MCU",
    io_library="gf180mcu_fd_io",
    input=[
        PadCellEntry("gf180mcu_fd_io__in_s", "Standard input pad", "gf180mcu_fd_io"),
        PadCellEntry("gf180mcu_fd_io__in_c", "Complementary input pad", "gf180mcu_fd_io"),
    ],
    output=[
        # GF180 does not ship a dedicated output-only pad in the open PDK;
        # bidirectional pads configured as output are used instead.
    ],
    bidirectional=[
        PadCellEntry("gf180mcu_fd_io__bi_24t", "24 mA bidirectional pad", "gf180mcu_fd_io"),
    ],
    analog=[
        PadCellEntry("gf180mcu_fd_io__asig_5p0", "5.0 V analog signal pad", "gf180mcu_fd_io"),
    ],
    power=[
        PadCellEntry("gf180mcu_fd_io__dvdd", "Digital VDD pad (ws_io)", "gf180mcu_ws_io"),
    ],
    ground=[
        PadCellEntry("gf180mcu_fd_io__dvss", "Digital VSS pad (ws_io)", "gf180mcu_ws_io"),
    ],
    corner=[
        PadCellEntry("gf180mcu_fd_io__cor", "Corner pad", "gf180mcu_fd_io"),
    ],
    filler=[
        PadCellEntry("gf180mcu_fd_io__fill1", "1x filler", "gf180mcu_fd_io"),
        PadCellEntry("gf180mcu_fd_io__fill5", "5x filler", "gf180mcu_fd_io"),
        PadCellEntry("gf180mcu_fd_io__fill10", "10x filler", "gf180mcu_fd_io"),
    ],
)

# Registry keyed by pdk_id — future PDKs add themselves here.
PAD_LIBRARIES: Dict[str, PadCellLibrary] = {
    GF180_PAD_LIBRARY.pdk_id: GF180_PAD_LIBRARY,
}


def get_pad_library(pdk_id: str) -> PadCellLibrary:
    """Look up the pad-cell library for *pdk_id*, or raise ``KeyError``."""
    if pdk_id not in PAD_LIBRARIES:
        raise KeyError(
            f"No pad-cell library registered for PDK '{pdk_id}'. "
            f"Available: {', '.join(sorted(PAD_LIBRARIES))}"
        )
    return PAD_LIBRARIES[pdk_id]


__all__ = [
    "PadCellEntry",
    "PadCellLibrary",
    "GF180_PAD_LIBRARY",
    "PAD_LIBRARIES",
    "get_pad_library",
]
