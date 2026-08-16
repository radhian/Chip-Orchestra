"""Block diagrams for the final report, drawn from the RTL itself.

A design report without a block diagram asks the reader to reconstruct the
architecture from prose and a file listing. This module renders two kinds of
figure directly from the Verilog on disk, so what the paper shows is what was
actually built rather than what someone remembered building:

* :func:`ip_symbol` — the conventional IP symbol for one module: a labelled box
  with its inputs entering on the left and its outputs leaving on the right,
  each annotated with its bit width.
* :func:`top_level_diagram` — the chip-level connection diagram: every instance
  inside the top module, the top's own pins, and an arrow for every net that
  carries data from the module that drives it to the modules that read it,
  laid out left to right in dependency order.

Output is TikZ (drawn at compile time, so the figures are vector art that scales
with the page) wrapped in a shrink-to-fit box — a diagram that runs past the
column is exactly the defect these figures exist to avoid.

Deliberately self-contained: `reporting` is imported by `agents`, so reaching
back into `agents` for a Verilog parser here would close an import cycle.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_TYPE_KW = {"wire", "reg", "logic", "signed", "unsigned", "var", "bit", "integer", "real"}
_INST_KEYWORDS = {
    "module", "endmodule", "begin", "end", "if", "else", "case", "endcase", "for",
    "while", "always", "assign", "initial", "generate", "endgenerate", "function",
    "endfunction", "task", "endtask", "posedge", "negedge", "input", "output",
    "inout", "wire", "reg", "parameter", "localparam", "integer", "genvar", "defparam",
}

_MODULE_RE = re.compile(r"\bmodule\s+(\w+)\s*(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
                        r"(\((?:[^()]|\([^()]*\))*\))?\s*;", re.S)
_INST_RE = re.compile(
    r"\b(\w+)\s*"
    r"(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
    r"(\w+)\s*"
    r"\(\s*(\.(?:[^()]|\([^()]*\))*)\)\s*;", re.S)
_CONN_RE = re.compile(r"\.\s*(\w+)\s*\(\s*([^()]*?)\s*\)")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def _constants(rtl_dir: Path) -> Dict[str, int]:
    """`define / parameter integers, so a `[`DATA_W-1:0]` port reports 8 bits."""
    out: Dict[str, int] = {}

    def _num(token: str) -> Optional[int]:
        token = re.sub(r"_", "", token.strip().rstrip(";").strip())
        sized = re.match(r"^\d*'([dhbo])([0-9a-fA-F]+)$", token)
        if sized:
            try:
                return int(sized.group(2), {"d": 10, "h": 16, "b": 2, "o": 8}[sized.group(1).lower()])
            except ValueError:
                return None
        try:
            return int(token, 0)
        except ValueError:
            return None

    for path in sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.v")):
        try:
            body = _strip_comments(path.read_text(errors="replace"))
        except OSError:
            continue
        for name, value in re.findall(r"`define\s+([A-Za-z_]\w*)\s+([^\n]+)", body):
            parsed = _num(value)
            if parsed is not None:
                out.setdefault(name, parsed)
        for name, value in re.findall(r"\bparameter\s+(?:integer\s+)?([A-Za-z_]\w*)\s*=\s*([^,;)\n]+)", body):
            parsed = _num(value)
            if parsed is not None:
                out.setdefault(name, parsed)
    return out


def _width(expr: str, consts: Dict[str, int]) -> int:
    """Bit width of a ``[msb:lsb]`` range (1 for a scalar, 0 when unresolvable)."""
    body = expr.strip().strip("[]")
    if ":" not in body:
        return 1 if not body else 0

    def _eval(part: str) -> Optional[int]:
        part = part.replace("`", "")
        for name, value in consts.items():
            part = re.sub(r"\b" + re.escape(name) + r"\b", str(value), part)
        if not re.fullmatch(r"[0-9+\-*/() ]+", part.strip() or "x"):
            return None
        try:
            return int(eval(part, {"__builtins__": {}}, {}))  # noqa: S307 - arithmetic only
        except Exception:  # noqa: BLE001
            return None

    msb, lsb = body.split(":", 1)
    hi, lo = _eval(msb), _eval(lsb)
    return abs(hi - lo) + 1 if hi is not None and lo is not None else 0


def _ports(module_text: str, consts: Dict[str, int]) -> List[Dict[str, Any]]:
    ports: List[Dict[str, Any]] = []
    seen = set()
    for match in re.finditer(
        r"\b(input|output|inout)\b((?:(?!\b(?:input|output|inout)\b)[^;)])*)", module_text
    ):
        direction, decl = match.group(1), match.group(2)
        width_match = re.search(r"\[[^\]]*\]", decl)
        width = _width(width_match.group(0) if width_match else "", consts)
        for name in re.findall(r"\b([A-Za-z_]\w*)\b", re.sub(r"\[[^\]]*\]", " ", decl)):
            if name in _TYPE_KW or name in seen:
                continue
            seen.add(name)
            ports.append({"name": name, "dir": direction, "width": width})
    return ports


def parse_design(rtl_dir: Path) -> Dict[str, Any]:
    """``{"modules": {name: {file, ports}}, "insts": {parent: [{child, inst, conns}]}}``.

    ``conns`` maps each connected port to the expression wired to it, which is
    what turns a list of instances into an actual connection graph."""
    rtl_dir = Path(rtl_dir)
    design: Dict[str, Any] = {"modules": {}, "insts": {}}
    if not rtl_dir.is_dir():
        return design
    consts = _constants(rtl_dir)
    for path in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        try:
            clean = _strip_comments(path.read_text(errors="replace"))
        except OSError:
            continue
        for match in _MODULE_RE.finditer(clean):
            name = match.group(1)
            if name in design["modules"]:
                continue
            end = clean.find("endmodule", match.end())
            body = clean[match.start(): end if end != -1 else len(clean)]
            design["modules"][name] = {"file": path.name, "ports": _ports(body, consts)}
            found = []
            for inst_match in _INST_RE.finditer(clean[match.end(): end if end != -1 else len(clean)]):
                child, inst, conns = inst_match.group(1), inst_match.group(2), inst_match.group(3)
                if child in _INST_KEYWORDS or inst in _INST_KEYWORDS:
                    continue
                found.append({"child": child, "inst": inst,
                              "conns": {port: net for port, net in _CONN_RE.findall(conns)}})
            design["insts"][name] = found
    return design


# --------------------------------------------------------------------------- #
# TikZ rendering
# --------------------------------------------------------------------------- #
_TIKZ_PREAMBLE = (
    "\\usepackage{tikz}\n"
    "\\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc}\n"
    "\\tikzset{\n"
    "  ipblock/.style   = {draw=black!75, thick, rounded corners=2pt, fill=black!5,\n"
    "                      align=center, inner sep=4pt, minimum height=9mm},\n"
    "  padnode/.style   = {draw=black!60, fill=white, rounded corners=6pt, align=center,\n"
    "                      inner sep=3pt, font=\\scriptsize\\ttfamily},\n"
    "  netedge/.style   = {-{Latex[length=4pt]}, draw=black!65, thick},\n"
    "  netlabel/.style  = {font=\\tiny\\ttfamily, fill=white, fill opacity=0.85,\n"
    "                      text opacity=1, inner sep=1pt,\n"
    "                      text=black!70, midway},\n"
    "  pinlabel/.style  = {font=\\tiny\\ttfamily, inner sep=1pt},\n"
    "}\n"
)


def _tex(name: str) -> str:
    """Escape an identifier for LaTeX and allow it to break at its separators —
    an unbreakable 34-character module name is what pushed a table cell over the
    column edge and into its neighbour."""
    escaped = str(name).replace("\\", "").replace("_", r"\_")
    return re.sub(r"(\\_|/|\.|-)", r"\1\\allowbreak{}", escaped)


def _tt(name: str) -> str:
    return r"\texttt{" + _tex(name) + "}"


def shrink_to_fit(body: str, target: str = r"\columnwidth") -> str:
    """Scale content down to the text measure, never up. ``\\resizebox`` alone
    would blow a two-pin symbol up to full width; the ``\\ifdim`` guard keeps
    small figures at their natural size and only rescues the oversized ones."""
    return (f"\\resizebox{{\\ifdim\\width>{target}{target}\\else\\width\\fi}}{{!}}{{%\n"
            f"{body}}}\n")


def _pin_label(port: Dict[str, Any]) -> str:
    width = port.get("width") or 1
    suffix = f"[{width - 1}:0]" if width and width > 1 else ""
    return _tex(port["name"]) + (r"\,\scriptsize" + _tex(suffix) if suffix else "")


def ip_symbol(module: str, ports: List[Dict[str, Any]], max_pins: int = 14) -> str:
    """The IP symbol for one module: inputs entering left, outputs leaving right.

    Returns a TikZ picture (already shrink-wrapped to the column), or '' when
    the module has no ports worth drawing."""
    inputs = [p for p in ports if p["dir"] == "input"]
    outputs = [p for p in ports if p["dir"] in ("output", "inout")]
    if not inputs and not outputs:
        return ""
    # A module with 30 pins draws as an unreadable comb; keep the first ones and
    # say honestly that the rest were elided.
    in_extra = max(0, len(inputs) - max_pins)
    out_extra = max(0, len(outputs) - max_pins)
    inputs, outputs = inputs[:max_pins], outputs[:max_pins]

    pitch = 0.52
    rows = max(len(inputs), len(outputs), 1)
    height = max(1.6, rows * pitch + 0.5)
    lines: List[str] = [
        "\\begin{tikzpicture}[font=\\footnotesize]",
        f"\\node[ipblock, minimum width=3.6cm, minimum height={height:.2f}cm] (blk) at (0,0) "
        f"{{\\ttfamily\\bfseries {_tex(module)}}};",
    ]

    # The pin label sits OUTSIDE the stub, not over it: anchored on the stub's
    # far end and pointing away from the block. Labelling above the stub put
    # `sobel_out [7:0]` straight through the block's border.
    stub = 0.9

    def _rail(items: List[Dict[str, Any]], side: str) -> None:
        if not items:
            return
        top = (len(items) - 1) * pitch / 2.0
        for index, port in enumerate(items):
            y = top - index * pitch
            if side == "in":
                lines.append(f"\\draw[netedge] ([xshift=-{stub}cm]blk.west|-0,{y:.2f}) -- "
                             f"(blk.west|-0,{y:.2f});")
                lines.append(f"\\node[pinlabel, anchor=east] at "
                             f"([xshift=-{stub + 0.08}cm]blk.west|-0,{y:.2f}) "
                             f"{{{_pin_label(port)}}};")
            else:
                lines.append(f"\\draw[netedge] (blk.east|-0,{y:.2f}) -- "
                             f"([xshift={stub}cm]blk.east|-0,{y:.2f});")
                lines.append(f"\\node[pinlabel, anchor=west] at "
                             f"([xshift={stub + 0.08}cm]blk.east|-0,{y:.2f}) "
                             f"{{{_pin_label(port)}}};")

    _rail(inputs, "in")
    _rail(outputs, "out")
    if in_extra:
        lines.append(f"\\node[pinlabel, anchor=north east, text=black!55] at "
                     f"(blk.south west) {{+{in_extra} more inputs}};")
    if out_extra:
        lines.append(f"\\node[pinlabel, anchor=north west, text=black!55] at "
                     f"(blk.south east) {{+{out_extra} more outputs}};")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines) + "\n"


_CONTROL_RE = re.compile(
    r"^(i_)?(clk|clock|clk_i|clk_in|sys_clk|rst|reset|rstn|rst_n|resetn|reset_n|"
    r"nrst|arst|arstn|rst_async_n|rst_sync_n|clk_en|clken)$", re.I)


def _is_control(name: str) -> bool:
    """Clock/reset, by port or net name — the nets a block diagram leaves out."""
    return bool(_CONTROL_RE.match((name or "").strip()))


def _feedback_edges(nodes: List[str], edges: List[Tuple[str, str, str]]) -> set:
    """Indices of the edges that close a cycle, found by depth-first search.

    Every real design has feedback (a controller reading `done` from the block
    it started), and layering a cyclic graph by longest path simply pushes each
    node one rank further on every pass until the picture is one node wide and
    fifteen columns long. Break the cycles first, lay out the DAG, then draw the
    feedback arrows back across it."""
    adjacency: Dict[str, List[Tuple[str, int]]] = {}
    for index, (src, dst, _) in enumerate(edges):
        adjacency.setdefault(src, []).append((dst, index))
    state = {node: 0 for node in nodes}   # 0 unvisited, 1 on stack, 2 done
    back: set = set()

    for root in nodes:
        if state.get(root, 0):
            continue
        stack: List[Tuple[str, int]] = [(root, 0)]
        state[root] = 1
        while stack:
            node, cursor = stack[-1]
            children = adjacency.get(node, [])
            if cursor >= len(children):
                state[node] = 2
                stack.pop()
                continue
            stack[-1] = (node, cursor + 1)
            child, edge_index = children[cursor]
            if state.get(child, 0) == 1:
                back.add(edge_index)
            elif state.get(child, 0) == 0:
                state[child] = 1
                stack.append((child, 0))
    return back


def _layer_nodes(nodes: List[str], edges: List[Tuple[str, str, str]],
                 sources: List[str]) -> Dict[str, int]:
    """Longest-path layering over the design's acyclic skeleton."""
    back = _feedback_edges(nodes, edges)
    forward = [edge for index, edge in enumerate(edges) if index not in back]
    layer = {node: 0 for node in nodes}
    for _ in range(len(nodes) + 1):
        changed = False
        for src, dst, _net in forward:
            if dst in layer and src in layer and layer[dst] < layer[src] + 1:
                layer[dst] = layer[src] + 1
                changed = True
        if not changed:
            break
    for node in sources:
        layer[node] = 0
    return layer


def _compress_layers(layer: Dict[str, int], max_columns: int = 5) -> Dict[str, int]:
    """Merge adjacent ranks until the diagram is at most ``max_columns`` wide.

    A strict longest-path layering of this kind of design comes out nine ranks
    deep with one block in most of them; scaled to fit a two-column figure that
    is a 4-point smear. Merging the two adjacent ranks with the smallest
    combined population keeps the left-to-right dataflow reading while turning
    the picture back into something square enough to be legible."""
    ranks = sorted({value for value in layer.values()})
    if len(ranks) <= max_columns:
        return {node: ranks.index(value) for node, value in layer.items()}
    buckets: List[List[str]] = [[node for node, value in layer.items() if value == rank]
                                for rank in ranks]
    while len(buckets) > max_columns:
        pairs = [(len(buckets[i]) + len(buckets[i + 1]), i) for i in range(len(buckets) - 1)]
        _, index = min(pairs)
        buckets[index] = buckets[index] + buckets[index + 1]
        del buckets[index + 1]
    return {node: column for column, bucket in enumerate(buckets) for node in bucket}


def top_level_diagram(design: Dict[str, Any], top: str,
                      max_instances: int = 20) -> str:
    """The chip-level connection diagram: pins, instances and the nets between.

    An arrow is drawn from the block that DRIVES a net (the instance whose
    output port, or the chip pin, is attached to it) to every block that reads
    it, so the picture shows the real dataflow rather than a bag of boxes."""
    modules = design.get("modules", {})
    instances = (design.get("insts", {}) or {}).get(top, [])
    if not instances:
        return ""
    instances = instances[:max_instances]

    top_ports = modules.get(top, {}).get("ports", [])
    producers: Dict[str, str] = {}
    consumers: Dict[str, List[str]] = {}
    nodes: List[Tuple[str, str, str]] = []  # (id, label, kind)
    sources: List[str] = []
    sinks: List[str] = []

    for port in top_ports:
        node_id = "pad_" + port["name"]
        if _is_control(port["name"]):
            continue
        if port["dir"] == "input":
            nodes.append((node_id, _tex(port["name"]), "in"))
            producers.setdefault(port["name"], node_id)
            sources.append(node_id)
        elif port["dir"] == "output":
            nodes.append((node_id, _tex(port["name"]), "out"))
            consumers.setdefault(port["name"], []).append(node_id)
            sinks.append(node_id)

    for entry in instances:
        node_id = "inst_" + entry["inst"]
        nodes.append((node_id,
                      f"\\ttfamily\\bfseries {_tex(entry['child'])}"
                      f"\\\\[1pt]\\ttfamily\\scriptsize {_tex(entry['inst'])}", "inst"))
        child_ports = {p["name"]: p for p in modules.get(entry["child"], {}).get("ports", [])}
        for port, net in entry["conns"].items():
            net = net.strip()
            # Only NAMED nets connect blocks; a literal (8'd0) or an unconnected
            # port is not an edge, and drawing one would invent a dependency.
            if not re.fullmatch(r"[A-Za-z_]\w*", net):
                continue
            # Clock and reset reach every block, so drawing them turns the
            # dataflow into a star of twenty identical arrows and hides the one
            # thing the figure is for. Omitted here and stated in the caption,
            # which is the standard convention for a block diagram.
            if _is_control(port) or _is_control(net):
                continue
            direction = child_ports.get(port, {}).get("dir")
            if direction == "output":
                producers.setdefault(net, node_id)
            elif direction == "input":
                consumers.setdefault(net, []).append(node_id)

    node_ids = [n[0] for n in nodes]
    # One arrow per pair of blocks, labelled with the nets it carries: a
    # controller driving six signals into the same block is one connection in a
    # block diagram, not six overlapping arrows.
    pair_nets: Dict[Tuple[str, str], List[str]] = {}
    for net, src in producers.items():
        for dst in consumers.get(net, []):
            if src == dst or src not in node_ids or dst not in node_ids:
                continue
            carried = pair_nets.setdefault((src, dst), [])
            if net not in carried:
                carried.append(net)
    edges: List[Tuple[str, str, str]] = [
        (src, dst, ", ".join(nets[:2]) + (f" +{len(nets) - 2}" if len(nets) > 2 else ""))
        for (src, dst), nets in pair_nets.items()
    ]
    if not edges:
        return ""

    layer = _layer_nodes(node_ids, edges, sources)
    for node_id in sinks:
        layer[node_id] = max(layer.values()) + 1 if layer else 1
    # Chip pins with nothing attached are noise; INSTANCES are kept even when
    # they carry no data net, because a block diagram that silently omits a
    # block of the design is not a diagram of the design. A reset synchronizer
    # simply has no data edges once clock and reset are left out, and the
    # caption says so.
    connected = {src for src, _, _ in edges} | {dst for _, dst, _ in edges}
    nodes = [n for n in nodes if n[0] in connected or n[2] == "inst"]
    kept = {n[0] for n in nodes}
    layer = _compress_layers({node: rank for node, rank in layer.items() if node in kept})

    columns: Dict[int, List[Tuple[str, str, str]]] = {}
    for node in nodes:
        columns.setdefault(layer.get(node[0], 0), []).append(node)

    dx, dy = 4.4, 2.5
    lines: List[str] = ["\\begin{tikzpicture}[font=\\footnotesize]"]
    tallest = max((len(col) for col in columns.values()), default=1)
    for column_index in sorted(columns):
        column = columns[column_index]
        offset = (tallest - len(column)) / 2.0
        for row, (node_id, label, kind) in enumerate(column):
            x = column_index * dx
            y = -(row + offset) * dy
            style = "padnode" if kind in ("in", "out") else "ipblock, minimum width=2.9cm"
            lines.append(f"\\node[{style}] ({node_id}) at ({x:.2f},{y:.2f}) {{{label}}};")
    for src, dst, net in edges:
        span = layer.get(dst, 0) - layer.get(src, 0)
        if span <= 0:                       # feedback: arc above the flow
            options, position = "[bend left=24]", "0.5"
        elif span > 1:
            # A straight arrow spanning more than one column runs THROUGH the
            # blocks in between (uart_tx's output crossed a line buffer to reach
            # the pin). Arc it around them instead, and shift its label off the
            # midpoint so labels of parallel long edges do not pile up.
            options, position = f"[bend right={min(14 + 6 * span, 34)}]", "0.17"
        else:
            options, position = "", "0.5"
        lines.append(f"\\draw[netedge] ({src}) to{options} node[netlabel, pos={position}] "
                     f"{{{_tex(net)}}} ({dst});")
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines) + "\n"


def build_figures(rtl_dir: Path, top: str) -> Dict[str, Any]:
    """Everything the report needs: the top-level connection picture and one IP
    symbol per module. Never raises — a report without a diagram is worse than
    one with, but far better than no report."""
    result: Dict[str, Any] = {"preamble": _TIKZ_PREAMBLE, "top": "", "symbols": {},
                              "instances": []}
    try:
        design = parse_design(rtl_dir)
    except Exception:  # noqa: BLE001
        return result
    if not design.get("modules"):
        return result
    if top not in design["modules"]:
        # Fall back to the module nothing else instantiates.
        instantiated = {entry["child"] for entries in design["insts"].values() for entry in entries}
        remaining = [name for name in design["modules"] if name not in instantiated]
        top = remaining[0] if remaining else next(iter(design["modules"]))
    try:
        result["top"] = top_level_diagram(design, top)
    except Exception:  # noqa: BLE001
        result["top"] = ""
    result["instances"] = [{"child": entry["child"], "inst": entry["inst"]}
                           for entry in design["insts"].get(top, [])]
    for name, meta in design["modules"].items():
        try:
            symbol = ip_symbol(name, meta.get("ports", []))
        except Exception:  # noqa: BLE001
            symbol = ""
        if symbol:
            result["symbols"][name] = {"tikz": symbol, "file": meta.get("file", ""),
                                       "ports": meta.get("ports", [])}
    result["top_module"] = top
    return result


# --------------------------------------------------------------------------- #
# Compiling the figures OUTSIDE the paper
# --------------------------------------------------------------------------- #
DIAGRAM_PDF = "diagrams.pdf"
DIAGRAM_TEX = "diagrams.tex"


def compile_figures(figures: Dict[str, Any], out_dir: Path,
                    timeout: int = 180) -> Dict[str, int]:
    """Typeset the diagrams into a multi-page PDF, one cropped page per figure.

    The report does NOT load TikZ itself, and that is deliberate. The IEEE
    Access class builds its blue on a PANTONE spot colour through ``color`` +
    ``spotcolor``; TikZ pulls in ``xcolor``, the two are incompatible, and the
    resulting PDF carries a spot-colour space that renderers reject — every
    blue section heading and caption label in the paper silently disappeared.
    Compiling the pictures in their own document and including the pages as
    vector art keeps the diagrams AND the class's typography intact.

    Returns ``{figure_key: page_number}`` — empty when nothing could be built,
    in which case the report simply omits the figures.
    """
    top = figures.get("top") or ""
    symbols = figures.get("symbols") or {}
    if not top and not symbols:
        return {}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages: Dict[str, int] = {}
    body: List[str] = []
    if top:
        pages["__top__"] = len(body) + 1
        body.append(top)
    for name in sorted(symbols):
        picture = symbols[name].get("tikz") or ""
        if not picture:
            continue
        pages[name] = len(body) + 1
        body.append(picture)
    if not body:
        return {}

    source = (
        "% Block diagrams for the final report — compiled separately from the\n"
        "% paper so the report never has to load TikZ (and with it xcolor,\n"
        "% which is incompatible with the IEEE Access class's spot-colour blue).\n"
        "\\documentclass[multi=tikzpicture,crop,border=2pt]{standalone}\n"
        + (figures.get("preamble") or "") +
        "\\begin{document}\n" + "\n".join(body) + "\n\\end{document}\n"
    )
    (out_dir / DIAGRAM_TEX).write_text(source)

    import subprocess
    try:
        subprocess.run(["pdflatex", "-interaction=nonstopmode", DIAGRAM_TEX],
                       cwd=str(out_dir), capture_output=True, text=True,
                       errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return {}
    if not (out_dir / DIAGRAM_PDF).is_file():
        return {}
    for extension in (".aux", ".log"):
        (out_dir / (DIAGRAM_TEX[:-4] + extension)).unlink(missing_ok=True)
    return pages


def include_page(page: int, target: str = r"\columnwidth") -> str:
    """``\\includegraphics`` of one diagram page, shrunk to fit the measure."""
    return shrink_to_fit(f"\\includegraphics[page={page}]{{{DIAGRAM_PDF}}}", target)


__all__ = ["parse_design", "ip_symbol", "top_level_diagram", "build_figures",
           "compile_figures", "include_page", "shrink_to_fit",
           "DIAGRAM_PDF", "DIAGRAM_TEX"]
