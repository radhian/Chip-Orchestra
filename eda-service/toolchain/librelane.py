"""LibreLane PNR configuration and execution helpers.

The EDA API owns this translation so the orchestration DAG remains at the PNR
stage boundary.  No pad-cell names are inferred here: they are supplied by the
design workspace and validated against its top-level RTL where possible.

This module covers *both* Classic flows (no pad ring) and the Chip flow
(OpenROAD.PadRing) introduced for GF180 Chipathon-style tape-outs.
"""
from __future__ import annotations

import enum
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from runner import CommandResult, CommandRunner, default_runner


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PadManifestError(ValueError):
    """A deterministic, actionable pad-ring input error."""


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

class FailureCategory(str, enum.Enum):
    """Coarse failure bucket so the repair layer gets actionable context."""
    TOOLCHAIN = "TOOLCHAIN"
    PDK = "PDK"
    CONFIG = "CONFIG"
    PAD_RING = "PAD_RING"
    POWER = "POWER"
    FLOORPLAN = "FLOORPLAN"
    PLACEMENT = "PLACEMENT"
    CTS = "CTS"
    ROUTING = "ROUTING"
    DRC = "DRC"
    LVS = "LVS"
    GDS = "GDS"
    UNKNOWN = "UNKNOWN"


_FAILURE_PATTERNS: List[tuple[re.Pattern[str], FailureCategory]] = [
    (re.compile(r"(?i)pad.?ring|PAD_(SOUTH|EAST|NORTH|WEST|CFG)"), FailureCategory.PAD_RING),
    (re.compile(r"(?i)PDK|pdk_root|volare"), FailureCategory.PDK),
    (re.compile(r"(?i)floorplan|die.?area|core.?area"), FailureCategory.FLOORPLAN),
    (re.compile(r"(?i)placement|global.?place|detail.?place"), FailureCategory.PLACEMENT),
    (re.compile(r"(?i)CTS|clock.?tree"), FailureCategory.CTS),
    (re.compile(r"(?i)route|routing|global.?route|detail.?route"), FailureCategory.ROUTING),
    (re.compile(r"(?i)DRC|design.?rule"), FailureCategory.DRC),
    (re.compile(r"(?i)LVS|layout.?vs"), FailureCategory.LVS),
    (re.compile(r"(?i)GDS|stream.?out|GDSII"), FailureCategory.GDS),
    (re.compile(r"(?i)power|PDN|power.?grid"), FailureCategory.POWER),
    (re.compile(r"(?i)config|yaml|slot"), FailureCategory.CONFIG),
    (re.compile(r"(?i)librelane|openlane|openroad|not found|FileNotFound"), FailureCategory.TOOLCHAIN),
]


def classify_failure(log_text: str, failed_step: str = "") -> FailureCategory:
    """Best-effort classify a LibreLane failure from its log output."""
    combined = f"{failed_step}\n{log_text}"
    for pattern, category in _FAILURE_PATTERNS:
        if pattern.search(combined):
            return category
    return FailureCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Logical I/O requirements (user-facing, design-specific)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IORequirements:
    """Logical I/O counts requested by the user's chip specification.

    These are *requirements*, not physical instances.  The physical pad
    population is derived from these requirements plus the PDK's pad-cell
    library.

    Example: a design may need 4 digital inputs, 4 digital outputs,
    2 bidirectional, 1 analog — completely different from the 60-analog
    GF180 Chipathon workshop fixture.
    """
    inputs: int = 0
    outputs: int = 0
    bidirectional: int = 0
    analog: int = 0
    power: int = 0
    ground: int = 0
    corners: int = 4


def io_requirements_from_mapping(value: Dict[str, Any] | None) -> IORequirements:
    """Parse an ``io_requirements`` section from user config."""
    value = value or {}
    try:
        return IORequirements(
            inputs=int(value.get("inputs", 0)),
            outputs=int(value.get("outputs", 0)),
            bidirectional=int(value.get("bidirectional", 0)),
            analog=int(value.get("analog", 0)),
            power=int(value.get("power", 0)),
            ground=int(value.get("ground", 0)),
            corners=int(value.get("corners", 4)),
        )
    except (TypeError, ValueError) as exc:
        raise PadManifestError(f"io_requirements contains invalid values: {exc}") from exc


# ---------------------------------------------------------------------------
# Physical pad-ring configuration (per-side instance names)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PadRingConfig:
    """Physical pad-ring placement configuration.

    ``south/east/north/west`` are lists of physical pad INSTANCE names, because
    LibreLane's PAD_SOUTH / PAD_EAST / PAD_NORTH / PAD_WEST refer to physical
    pad instances.
    """
    enabled: bool = False
    cfg: str | None = None
    south: list[str] = field(default_factory=list)
    east: list[str] = field(default_factory=list)
    north: list[str] = field(default_factory=list)
    west: list[str] = field(default_factory=list)
    # Optional PDK identifier for pad-cell lookup.
    pdk_id: str = ""

    def sides(self) -> dict[str, list[str]]:
        return {"south": self.south, "east": self.east, "north": self.north, "west": self.west}

    def total_pads(self) -> int:
        return sum(len(v) for v in self.sides().values())


# ---------------------------------------------------------------------------
# Implementation config (Classic vs Chip)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImplementationConfig:
    flow: str = "Classic"
    pad_ring: PadRingConfig = field(default_factory=PadRingConfig)
    io_requirements: IORequirements = field(default_factory=IORequirements)


def implementation_from_mapping(value: dict[str, Any] | None) -> ImplementationConfig:
    """Parse an ``implementation`` section from user/workspace config."""
    value = value or {}
    flow = value.get("flow", "Classic")
    if flow not in {"Classic", "Chip"}:
        raise PadManifestError("implementation.flow must be either 'Classic' or 'Chip'")
    pad = value.get("pad_ring") or {}
    unknown = set(pad) - {"enabled", "cfg", "south", "east", "north", "west", "pdk_id"}
    if unknown:
        raise PadManifestError(f"pad_ring contains unsupported field(s): {', '.join(sorted(unknown))}")
    try:
        for side_key in ("south", "east", "north", "west"):
            val = pad.get(side_key, [])
            if isinstance(val, str):
                raise PadManifestError(
                    f"pad_ring.{side_key} must be a list of instance names, "
                    f"got string: {val!r}"
                )
        ring = PadRingConfig(
            enabled=bool(pad.get("enabled", False)), cfg=pad.get("cfg"),
            south=list(pad.get("south", [])), east=list(pad.get("east", [])),
            north=list(pad.get("north", [])), west=list(pad.get("west", [])),
            pdk_id=str(pad.get("pdk_id", "")),
        )
    except TypeError as exc:
        raise PadManifestError("pad_ring sides must be lists of instance names") from exc
    if flow == "Classic" and ring.enabled:
        raise PadManifestError("pad_ring.enabled requires implementation.flow='Chip'")

    io_req = io_requirements_from_mapping(value.get("io_requirements"))
    return ImplementationConfig(flow=flow, pad_ring=ring, io_requirements=io_req)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_pad_manifest(config: ImplementationConfig, workspace: Path) -> None:
    """Validate pad-ring configuration against the workspace.

    Checks for:
    - Empty instance names
    - Duplicate pad instances (within-side and cross-side)
    - Missing PAD_CFG file
    - Pad instances not found in workspace RTL
    """
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


# ---------------------------------------------------------------------------
# LibreLane config augmentation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Workspace materialization
# ---------------------------------------------------------------------------

_WORKSPACE_FILES = (
    # (source subdir, glob pattern, target subdir)
    ("src", "*.v", "rtl"),
    ("src", "*.sv", "rtl"),
    ("src", "*.svh", "rtl"),
    ("librelane", "config.yaml", "."),
    ("librelane/slots", "*.yaml", "librelane/slots"),
    ("librelane", "pdn_cfg.tcl", "librelane"),
    ("sdc", "*.sdc", "sdc"),
)


def materialize_workspace(
    source: Path,
    target: Path,
    *,
    extra_files: Sequence[tuple[str, str]] = (),
) -> List[str]:
    """Copy all referenced files from ``source`` into a flat ``target`` workspace.

    Returns a list of relative paths that were materialized.
    """
    target.mkdir(parents=True, exist_ok=True)
    materialized: List[str] = []

    for src_sub, pattern, tgt_sub in _WORKSPACE_FILES:
        src_dir = source / src_sub
        if not src_dir.is_dir():
            continue
        tgt_dir = target / tgt_sub
        tgt_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.glob(pattern):
            if f.is_file():
                dest = tgt_dir / f.name
                shutil.copy2(f, dest)
                materialized.append(str(dest.relative_to(target)))

    for src_rel, tgt_rel in extra_files:
        src_f = source / src_rel
        if src_f.is_file():
            tgt_f = target / tgt_rel
            tgt_f.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_f, tgt_f)
            materialized.append(tgt_rel)

    return materialized


# ---------------------------------------------------------------------------
# Chip flow execution (real LibreLane via subprocess or Docker)
# ---------------------------------------------------------------------------

# Default Docker image for standalone LibreLane Chip runs.
LIBRELANE_DOCKER_IMAGE = "ghcr.io/librelane/librelane:3.0.10"
LIBRELANE_CIEL_CACHE_VOLUME = "chip-orchestra-librelane-ciel-cache"


def _find_librelane_bin() -> Optional[str]:
    """Find the librelane binary on PATH."""
    return shutil.which(os.environ.get("LIBRELANE_BIN", "librelane"))


def run_chip_flow(
    workspace: Path,
    config_path: Path,
    *,
    runner: CommandRunner = default_runner,
    timeout: float = 7200,
    docker_image: str = "",
    use_docker: bool = False,
) -> Dict[str, Any]:
    """Execute LibreLane Chip flow and return structured result.

    If ``use_docker`` is True or ``librelane`` is not on PATH, runs via Docker.
    """
    workspace = Path(workspace)
    config_path = Path(config_path)

    # Try local binary first, fall back to Docker.
    executable = _find_librelane_bin()
    if executable and not use_docker:
        return _run_local(workspace, config_path, executable, runner, timeout)
    return _run_docker(workspace, config_path, docker_image or LIBRELANE_DOCKER_IMAGE, runner, timeout)


def _run_local(
    workspace: Path,
    config_path: Path,
    executable: str,
    runner: CommandRunner,
    timeout: float,
) -> Dict[str, Any]:
    """Run LibreLane Chip flow via local binary."""
    args = [executable, "--flow", "Chip", str(config_path)]
    result = runner.run(args, cwd=workspace, timeout=timeout)
    if not result.ok:
        category = classify_failure(result.output, "LibreLane Chip flow")
        raise RuntimeError(
            f"LibreLane Chip flow failed (exit {result.returncode}, "
            f"category={category.value}):\n{result.output}"
        )
    return {
        "summary": "LibreLane Chip flow completed.",
        "flow": "Chip",
        "command": result.args,
        "log": result.output,
        "exit_code": result.returncode,
        "execution_mode": "local",
    }


def _run_docker(
    workspace: Path,
    config_path: Path,
    image: str,
    runner: CommandRunner,
    timeout: float,
) -> Dict[str, Any]:
    """Run LibreLane Chip flow via Docker container."""
    # Docker run with:
    # - workspace mounted at /work
    # - Ciel cache volume for PDK persistence
    # - config path relative to /work
    config_rel = config_path.relative_to(workspace) if config_path.is_relative_to(workspace) else config_path.name
    config_rel_str = Path(config_rel).as_posix()
    args = [
        "docker", "run", "--rm",
        "-e", "PDK_ROOT=/opt/pdk",
        "-v", f"{workspace}:/work",
        "-v", "chip-orchestra_pdk_data:/opt/pdk",
        "-w", "/work",
        image,
        "librelane", "--flow", "Chip",
        config_rel_str,
    ]
    result = runner.run(args, cwd=workspace, timeout=timeout)
    if not result.ok:
        category = classify_failure(result.output, "LibreLane Chip flow (Docker)")
        raise RuntimeError(
            f"LibreLane Chip flow (Docker) failed (exit {result.returncode}, "
            f"category={category.value}):\n{result.output}"
        )
    return {
        "summary": "LibreLane Chip flow completed (Docker).",
        "flow": "Chip",
        "command": result.args,
        "log": result.output,
        "exit_code": result.returncode,
        "execution_mode": "docker",
        "image": image,
    }


# ---------------------------------------------------------------------------
# Artifact collection from a completed Chip flow run
# ---------------------------------------------------------------------------

def collect_chip_artifacts(run_dir: Path) -> Dict[str, Any]:
    """Scan a completed LibreLane Chip run directory for output artifacts.

    Returns paths to ODB, DEF, GDS, state_out.json, and extracts metrics.
    """
    artifacts: Dict[str, Any] = {"run_dir": str(run_dir)}

    # state_out.json — LibreLane's final state dump
    state_out = run_dir / "state_out.json"
    if state_out.is_file():
        artifacts["state_out"] = str(state_out)
        try:
            state = json.loads(state_out.read_text(encoding="utf-8"))
            artifacts["state_summary"] = {
                "flow": state.get("flow", ""),
                "pdk": state.get("pdk", ""),
                "design_name": state.get("design_name", ""),
                "step_count": len(state.get("steps", [])),
            }
        except (json.JSONDecodeError, OSError):
            pass

    # Scan for ODB, DEF, GDS files
    for ext, key in [("*.odb", "odb"), ("*.def", "def"), ("*.gds", "gds"), ("*.gds2", "gds")]:
        found = sorted(run_dir.rglob(ext))
        if found:
            artifacts[key] = [str(f) for f in found]

    # LibreLane logs
    log_files = sorted(run_dir.rglob("*.log"))
    if log_files:
        artifacts["logs"] = [str(f) for f in log_files[:10]]

    # Metrics/reports
    report_files = sorted(run_dir.rglob("*.rpt"))
    if report_files:
        artifacts["reports"] = [str(f) for f in report_files[:20]]

    return artifacts


# ---------------------------------------------------------------------------
# Pad placement extraction from DEF or ODB
# ---------------------------------------------------------------------------

def extract_pad_placement_from_def(def_path: Path) -> List[Dict[str, Any]]:
    """Parse pad instance placement from a DEF file.

    Returns a list of dicts: {instance, master, side, x, y}.
    Side is inferred from coordinates relative to die area.
    """
    text = def_path.read_text(encoding="utf-8", errors="ignore")
    placements: List[Dict[str, Any]] = []

    # Parse DIEAREA to determine dimensions
    die_match = re.search(r"DIEAREA\s+\(\s*(\d+)\s+(\d+)\s*\)\s+\(\s*(\d+)\s+(\d+)\s*\)", text)
    die_x_max, die_y_max = 0.0, 0.0
    dbu = 1000.0  # default database units per micron
    if die_match:
        die_x_max = float(die_match.group(3)) / dbu
        die_y_max = float(die_match.group(4)) / dbu

    # Parse COMPONENTS section for pad instances
    in_components = False
    current_inst = ""
    current_master = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("COMPONENTS"):
            in_components = True
            continue
        if stripped.startswith("END COMPONENTS"):
            break
        if not in_components:
            continue
        if stripped.startswith("-"):
            parts = stripped.split()
            if len(parts) >= 3:
                current_inst = parts[1]
                current_master = parts[2]
        # Look for PLACED or FIXED coordinates
        placed_match = re.search(r"(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)", stripped)
        if placed_match and current_inst:
            x = float(placed_match.group(1)) / dbu
            y = float(placed_match.group(2)) / dbu
            side = _infer_side(x, y, die_x_max, die_y_max)
            placements.append({
                "instance": current_inst,
                "master": current_master,
                "side": side,
                "x": round(x, 3),
                "y": round(y, 3),
            })
            current_inst = ""

    return placements


def _infer_side(x: float, y: float, die_w: float, die_h: float) -> str:
    """Infer which die side a pad sits on from its coordinates."""
    if die_w <= 0 or die_h <= 0:
        return "unknown"
    # Relative position
    rx = x / die_w if die_w > 0 else 0.5
    ry = y / die_h if die_h > 0 else 0.5
    # Corners: pad must be close to both edges simultaneously.
    # Use a tight threshold: both rx and ry within 2% of a corner.
    if (rx < 0.02 or rx > 0.98) and (ry < 0.02 or ry > 0.98):
        return "corner"
    # Edge: whichever edge is closest
    distances = [
        ("south", ry),
        ("west", rx),
        ("north", 1.0 - ry),
        ("east", 1.0 - rx),
    ]
    return min(distances, key=lambda d: d[1])[0]


def write_pad_placement_json(placements: List[Dict[str, Any]], output_path: Path) -> None:
    """Write pad placement data as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(placements, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Observability: log parsing for Chip flow stage visibility
# ---------------------------------------------------------------------------

_STAGE_PATTERNS = [
    (re.compile(r"OpenROAD\.PadRing", re.I), "OpenROAD.PadRing"),
    (re.compile(r"OpenROAD\.Floorplan", re.I), "Floorplan"),
    (re.compile(r"OpenROAD\.(?:GlobalPlace|DetailPlace)", re.I), "Placement"),
    (re.compile(r"OpenROAD\.CTS", re.I), "CTS"),
    (re.compile(r"OpenROAD\.(?:GlobalRoute|DetailRoute)", re.I), "Routing"),
    (re.compile(r"KLayout\.(?:StreamOut|DRC)", re.I), "GDS/DRC"),
    (re.compile(r"(?:Checker\.)?LVS", re.I), "LVS"),
    (re.compile(r"Magic\.(?:StreamOut|DRC)", re.I), "Magic"),
]


def parse_librelane_stages(log_text: str) -> List[str]:
    """Extract the LibreLane stages that appear in a run log."""
    seen: List[str] = []
    for pattern, label in _STAGE_PATTERNS:
        if pattern.search(log_text) and label not in seen:
            seen.append(label)
    return seen


def extract_librelane_version(log_text: str) -> str:
    """Extract LibreLane version from log text."""
    match = re.search(r"LibreLane\s+v?([\d.]+)", log_text)
    return match.group(1) if match else ""


__all__ = [
    "PadManifestError",
    "FailureCategory",
    "classify_failure",
    "IORequirements",
    "io_requirements_from_mapping",
    "PadRingConfig",
    "ImplementationConfig",
    "implementation_from_mapping",
    "validate_pad_manifest",
    "apply_pad_ring",
    "materialize_workspace",
    "run_chip_flow",
    "collect_chip_artifacts",
    "extract_pad_placement_from_def",
    "write_pad_placement_json",
    "parse_librelane_stages",
    "extract_librelane_version",
    "LIBRELANE_DOCKER_IMAGE",
]
