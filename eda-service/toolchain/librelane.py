"""LibreLane PNR configuration and execution helpers.

The EDA API owns this translation so the orchestration DAG remains at the PNR
stage boundary.  No pad-cell names are inferred here: they are supplied by the
design workspace and validated against its top-level RTL where possible.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PadManifestError(ValueError):
    """A deterministic, actionable pad-ring input error."""


@dataclass(frozen=True)
class PadRingConfig:
    enabled: bool = False
    cfg: str | None = None
    south: list[str] = field(default_factory=list)
    east: list[str] = field(default_factory=list)
    north: list[str] = field(default_factory=list)
    west: list[str] = field(default_factory=list)

    def sides(self) -> dict[str, list[str]]:
        return {"south": self.south, "east": self.east, "north": self.north, "west": self.west}


@dataclass(frozen=True)
class ImplementationConfig:
    flow: str = "Classic"
    pad_ring: PadRingConfig = field(default_factory=PadRingConfig)


def implementation_from_mapping(value: dict[str, Any] | None) -> ImplementationConfig:
    value = value or {}
    flow = value.get("flow", "Classic")
    if flow not in {"Classic", "Chip"}:
        raise PadManifestError("implementation.flow must be either 'Classic' or 'Chip'")
    pad = value.get("pad_ring") or {}
    unknown = set(pad) - {"enabled", "cfg", "south", "east", "north", "west"}
    if unknown:
        raise PadManifestError(f"pad_ring contains unsupported field(s): {', '.join(sorted(unknown))}")
    try:
        ring = PadRingConfig(
            enabled=bool(pad.get("enabled", False)), cfg=pad.get("cfg"),
            south=list(pad.get("south", [])), east=list(pad.get("east", [])),
            north=list(pad.get("north", [])), west=list(pad.get("west", [])),
        )
    except TypeError as exc:
        raise PadManifestError("pad_ring sides must be lists of instance names") from exc
    if flow == "Classic" and ring.enabled:
        raise PadManifestError("pad_ring.enabled requires implementation.flow='Chip'")
    return ImplementationConfig(flow=flow, pad_ring=ring)


def validate_pad_manifest(config: ImplementationConfig, workspace: Path) -> None:
    if config.flow != "Chip" or not config.pad_ring.enabled:
        return
    all_pads: list[tuple[str, str]] = [(side, pad) for side, pads in config.pad_ring.sides().items() for pad in pads]
    seen: dict[str, str] = {}
    for side, pad in all_pads:
        if not isinstance(pad, str) or not pad.strip():
            raise PadManifestError(f"pad_ring.{side} contains an empty pad instance name")
        if pad in seen:
            raise PadManifestError(f"pad instance '{pad}' is configured on both {seen[pad]} and {side} sides")
        seen[pad] = side
    if config.pad_ring.cfg:
        cfg = workspace / config.pad_ring.cfg
        if not cfg.is_file():
            raise PadManifestError(f"PAD_CFG does not exist: {config.pad_ring.cfg}")
    rtl_files = sorted([*workspace.rglob("*.v"), *workspace.rglob("*.sv")]) if workspace.is_dir() else []
    if seen and not rtl_files:
        raise PadManifestError("cannot validate pad instances: no top-level RTL/Verilog files found in workspace")
    rtl = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in rtl_files)
    for pad in sorted(seen):
        if not re.search(r"\b" + re.escape(pad) + r"\b", rtl):
            raise PadManifestError(f"configured pad instance '{pad}' does not exist in workspace RTL")


def apply_pad_ring(config_json: dict[str, Any], config: ImplementationConfig, workspace: Path) -> dict[str, Any]:
    """Return a LibreLane config copy with only Chip pad-ring variables added."""
    result = dict(config_json)
    if config.flow != "Chip":
        return result
    if config.pad_ring.enabled:
        validate_pad_manifest(config, workspace)
        if config.pad_ring.cfg:
            result["PAD_CFG"] = config.pad_ring.cfg
        for key, pads in (("PAD_SOUTH", config.pad_ring.south), ("PAD_EAST", config.pad_ring.east),
                          ("PAD_NORTH", config.pad_ring.north), ("PAD_WEST", config.pad_ring.west)):
            if pads:
                result[key] = pads
    return result


def run_chip_flow(workspace: Path, config_path: Path) -> dict[str, Any]:
    executable = shutil.which("librelane")
    if executable is None:
        raise RuntimeError("LibreLane executable not found; Chip flow requires a LibreLane/PDK-enabled EDA environment")
    completed = subprocess.run(
        [executable, "--flow", "Chip", str(config_path)], cwd=workspace,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"LibreLane Chip flow failed (exit {completed.returncode}):\n{completed.stdout}")
    return {"summary": "LibreLane Chip flow completed.", "flow": "Chip", "command": [executable, "--flow", "Chip", str(config_path)], "log": completed.stdout}
