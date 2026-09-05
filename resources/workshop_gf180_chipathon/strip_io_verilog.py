"""Generate a Yosys- and OpenSTA-compatible blackbox model of the GF180
``gf180mcu_fd_io`` pad library.

The upstream ``gf180mcu_fd_io.v`` shipped with the PDK is a gate/transistor
level behavioural model.  It is full of constructs that neither Yosys nor
OpenSTA's Verilog front-ends accept when elaborating the chip top:

  * Verilog-1995 switch primitives (``rnmos`` / ``rpmos`` / ``pmos`` / ``nmos``)
  * ```delay_mode_path`` / ```delay_mode_unit`` / ```delay_mode_distributed``
    compiler directives (Yosys ``json_header`` rejects these)
  * ``specify`` / ``endspecify`` timing blocks and system timing checks
  * gate primitives with delays such as ``and #1 (...)`` / ``bufif1 #1 (...)``
    (OpenSTA's reader raises a syntax error on these)

For place-and-route we only need the pad module *interfaces* (port names and
directions), not their internals — the physical implementation comes from the
LEF/GDS (see ``PAD_LEFS`` / ``PAD_GDS`` in ``librelane/config.yaml``).

This script therefore extracts each module's port interface and emits an empty
blackbox stub.  A leading ``/// sta-blackbox`` marker tells OpenSTA to treat
every module in the file as a blackbox, since the pads carry no timing liberty.

Usage (inside the eda-service / LibreLane container, PDK mounted at PDK_ROOT):
    python3 strip_io_verilog.py

Paths may be overridden via environment variables:
    GF180_IO_SRC   source gf180mcu_fd_io.v (default: under $PDK_ROOT/gf180mcuD)
    GF180_IO_DEST  destination blackbox file
"""
import os
import re
import sys

_PDK_ROOT = os.environ.get("PDK_ROOT", "/opt/pdk")
SRC = os.environ.get(
    "GF180_IO_SRC",
    os.path.join(
        _PDK_ROOT,
        "gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v",
    ),
)
DEST = os.environ.get(
    "GF180_IO_DEST",
    "/resources/workshop_gf180_chipathon/gf180mcu_fd_io_yosys.v",
)

# Non-ANSI port direction declarations inside a module body.
PORT_DECL_RE = re.compile(r"^(input|output|inout)\b.*;$")
MODULE_RE = re.compile(r"module\s+(\w+)\s*\((.*?)\)\s*;(.*?)\bendmodule", re.S)


def build_blackboxes(src: str) -> tuple[str, int]:
    """Return (blackbox_text, module_count) for the given library source."""
    modules = MODULE_RE.findall(src)
    if not modules:
        raise ValueError("no Verilog modules found in source")

    out = [
        "/// sta-blackbox",
        "// Auto-generated blackbox interfaces for the GF180 gf180mcu_fd_io pad",
        "// library.  DO NOT EDIT BY HAND — regenerate with strip_io_verilog.py.",
        "// Only the module port interfaces are kept; internals are intentionally",
        "// empty so Yosys and OpenSTA treat every pad cell as a blackbox.  The",
        "// physical view comes from PAD_LEFS / PAD_GDS in librelane/config.yaml.",
        "",
    ]
    for name, ports, body in modules:
        ports = re.sub(r"\s+", " ", ports).strip()
        out.append(f"module {name} ({ports});")
        for line in body.splitlines():
            stripped = line.strip()
            if PORT_DECL_RE.match(stripped):
                out.append("\t" + stripped)
        out.append("endmodule")
        out.append("")

    return "\n".join(out), len(modules)


def main() -> None:
    try:
        with open(SRC) as fh:
            src = fh.read()
    except OSError as exc:
        sys.exit(f"cannot read source library {SRC!r}: {exc}")

    try:
        text, count = build_blackboxes(src)
    except ValueError as exc:
        sys.exit(f"{SRC}: {exc}")

    with open(DEST, "w") as fh:
        fh.write(text)
    print(f"Wrote {count} blackbox modules to {DEST}")


if __name__ == "__main__":
    main()
