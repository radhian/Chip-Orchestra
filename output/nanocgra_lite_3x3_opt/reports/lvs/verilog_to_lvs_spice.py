#!/usr/bin/env python3
"""Convert powered post-route Verilog to hierarchical LVS SPICE using official PDK CDL pin order."""
import argparse
import re
from pathlib import Path

TOP_PORTS = [
    "vss", "clk_PU", "clk_PD", "clk", "rst_n_PU", "rst_n_PD", "rst_n",
    "uart_rx_PU", "uart_rx_PD", "uart_rx", "uart_tx_CS", "uart_tx_SL",
    "uart_tx_IE", "uart_tx_OE", "uart_tx_PU", "uart_tx_PD", "uart_tx_OUT",
    "uart_tx_PDRV0", "uart_tx_PDRV1", "uart_tx_IN", "vdd",
]


def normalize(name: str) -> str:
    name = name.strip()
    if name.startswith("\\"):
        name = name[1:].strip()
    constants = {
        "1'b0": "vss", "1'h0": "vss", "1'd0": "vss", "0": "vss",
        "1'b1": "vdd", "1'h1": "vdd", "1'd1": "vdd", "1": "vdd",
    }
    if name in constants:
        return constants[name]
    return re.sub(r"[^A-Za-z0-9_./\[\]-]", "_", name)


def parse_cdl_pins(text: str) -> dict[str, list[str]]:
    lines = text.splitlines()
    result: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        match = re.match(r"\s*\.subckt\s+(\S+)\s*(.*)", lines[index], re.I)
        if not match:
            index += 1
            continue
        name = match.group(1)
        fields = match.group(2).split()
        index += 1
        while index < len(lines) and re.match(r"\s*\+", lines[index]):
            fields.extend(re.sub(r"^\s*\+", "", lines[index]).split())
            index += 1
        result[name] = fields
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verilog", required=True, type=Path)
    parser.add_argument("--cdl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    verilog = args.verilog.read_text()
    cell_pins = parse_cdl_pins(args.cdl.read_text(errors="replace"))

    parent: dict[str, str] = {}

    def find(name: str) -> str:
        parent.setdefault(name, name)
        if parent[name] != name:
            parent[name] = find(parent[name])
        return parent[name]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        preferred = min((left_root, right_root), key=lambda value: (value not in TOP_PORTS, len(value), value))
        parent[right_root if preferred == left_root else left_root] = preferred

    for left, right in re.findall(r"\bassign\s+([^=;]+?)\s*=\s*([^;]+?)\s*;", verilog, re.S):
        union(normalize(left), normalize(right))

    instance_re = re.compile(
        r"\b(gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]+)\s+"
        r"(\\[^\s(]+|[A-Za-z0-9_$./\[\]-]+)\s*\((.*?)\);",
        re.S,
    )
    connection_re = re.compile(r"\.([A-Za-z0-9_]+)\s*\(\s*([^()]*)\)", re.S)
    output = [
        "* Source LVS SPICE generated from powered post-route Verilog",
        "* Standard-cell pin order comes only from the official GF180MCU CDL",
        ".subckt NanoCGRA_Lite " + " ".join(TOP_PORTS),
    ]
    missing_cells: set[str] = set()
    instances = 0
    for cell, instance, body in instance_re.findall(verilog):
        pins = cell_pins.get(cell)
        if pins is None:
            missing_cells.add(cell)
            continue
        connections = {pin: normalize(net) for pin, net in connection_re.findall(body) if net.strip()}
        ordered = []
        for pin in pins:
            if pin in connections:
                ordered.append(find(connections[pin]))
            elif pin in {"VDD", "VNW"}:
                ordered.append("vdd")
            elif pin in {"VSS", "VPW"}:
                ordered.append("vss")
            else:
                raise SystemExit(f"instance {instance} ({cell}) has no connection for required pin {pin}")
        output.append("X" + normalize(instance) + " " + " ".join(ordered) + " " + cell)
        instances += 1
    output.extend([".ends NanoCGRA_Lite", ""])
    if missing_cells:
        raise SystemExit("missing official CDL definitions: " + ", ".join(sorted(missing_cells)))
    args.output.write_text("\n".join(output))
    print(f"wrote {args.output} with {instances} instances and {len(cell_pins)} official cell definitions")


if __name__ == "__main__":
    main()
