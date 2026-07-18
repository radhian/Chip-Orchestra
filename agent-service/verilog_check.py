"""
Deterministic Verilog structure checks — the pipeline's safety net.

A small local model WILL produce incoherent multi-file designs (modules that
reference macros without `include`, top modules that instantiate ports that
don't exist, duplicate alu.v/alu_8bit.v variants). LLM retries cannot converge
against 70 cross-module elaboration errors. These checks catch every one of
those failure classes DETERMINISTICALLY, at the earliest possible moment:

  • check_file()       — compile ONE file with `iverilog -t null -i` the moment
                         it is written, so the generating agent gets the error
                         back in the same tool call and fixes it immediately.
  • static_report()    — cross-module audit before simulation: duplicate module
                         definitions, instantiations of unknown modules, named
                         port connections that don't exist on the definition,
                         bare uses of `define macros (missing backtick/include).
  • pick_top()         — structural top detection that prefers an actual
                         integration module over a leaf that nobody happens to
                         instantiate.
  • closure_files()    — the dependency cone from the top module, so simulation
                         compiles ONLY the files the design actually uses and a
                         stale/orphan file can never break the build.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Verilog keywords that look like instantiations in a naive scan.
_KEYWORDS = {
    "module", "endmodule", "begin", "end", "if", "else", "case", "casez", "casex",
    "endcase", "for", "while", "repeat", "forever", "always", "initial", "assign",
    "wire", "reg", "integer", "real", "genvar", "generate", "endgenerate", "input",
    "output", "inout", "parameter", "localparam", "function", "endfunction", "task",
    "endtask", "posedge", "negedge", "or", "and", "not", "nand", "nor", "xor",
    "xnor", "buf", "bufif0", "bufif1", "notif0", "notif1", "supply0", "supply1",
    "default", "signed", "unsigned", "specify", "endspecify", "defparam",
}

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_MODULE_RE = re.compile(r"\bmodule\s+(\w+)\s*(#\s*\(.*?\))?\s*(\(.*?\))?\s*;",
                        re.DOTALL)
_DEFINE_RE = re.compile(r"`define\s+(\w+)")
# named instantiation:  mod_name [#(.P(v), ...)] inst_name ( .port(sig), ... );
# The param-override and port lists are matched with ONE level of nested parens balanced
# (`(?:[^()]|\([^()]*\))*`), so SystemVerilog instantiations like
#   fazyrv_core #(.CHUNKSIZE(CHUNKSIZE)) i_core (.clk_i(clk_i), ...);
# are detected (the old `[^;]*?` stopped at the first inner `)` → 0 instantiations on SV → no
# top found → the testbench tested a leaf module).
_INST_RE = re.compile(
    r"\b(\w+)\s*"
    r"(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"          # optional #(params), 1-level nesting
    r"(\w+)\s*"                                        # instance name
    r"\(\s*(\.(?:[^()]|\([^()]*\))*)\)\s*;",           # port list (.x(y), …), 1-level nesting
    re.DOTALL)
_NAMED_PORT_RE = re.compile(r"\.(\w+)\s*\(")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def autofix_text(code: str) -> Tuple[str, List[str]]:
    """Deterministically repair the UNAMBIGUOUS syntax tics a small model emits, so the
    LLM correction loop never has to spend a cycle on them. Returns (fixed, notes).

    The big one: `}` used to CLOSE A BLOCK instead of `end` (qwen does this constantly:
    `... end; } else if (...)`). We tell a block-close `}` from a concatenation `}` by
    tracking `{` depth while skipping strings/comments — a `}` seen at brace-depth 0 is a
    misused block close and becomes `end`; a `}` inside `{...}` is left alone. Conservative
    by construction: a real concatenation always has a matching earlier `{`, so it is never
    touched."""
    if not code or "}" not in code:
        return code, []
    out: List[str] = []
    depth = 0          # concatenation/replication brace depth
    i, n = 0, len(code)
    fixed_braces = 0
    while i < n:
        c = code[i]
        # skip line comment
        if c == "/" and i + 1 < n and code[i + 1] == "/":
            j = code.find("\n", i)
            j = n if j == -1 else j
            out.append(code[i:j])
            i = j
            continue
        # skip block comment
        if c == "/" and i + 1 < n and code[i + 1] == "*":
            j = code.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(code[i:j])
            i = j
            continue
        # skip string literal
        if c == '"':
            j = i + 1
            while j < n and code[j] != '"':
                j += 2 if code[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(code[i:j])
            i = j
            continue
        if c == "{":
            depth += 1
            out.append(c)
            i += 1
            continue
        if c == "}":
            if depth > 0:                       # real concatenation close — leave it
                depth -= 1
                out.append(c)
                i += 1
                continue
            # depth 0 → misused block close → `end`
            fixed_braces += 1
            out.append("end")
            i += 1
            if i < n and code[i] == ";":        # `};` → `end`
                i += 1
            if i < n and (code[i].isalnum() or code[i] == "_"):
                out.append(" ")                 # `}else` → `end else`
            continue
        out.append(c)
        i += 1
    notes = []
    if fixed_braces:
        notes.append(f"replaced {fixed_braces} misused `}}` block-close(s) with `end`")
    return "".join(out), notes


def _port_names(header: str) -> List[str]:
    """Port names from a module's `(...)` header (ANSI or non-ANSI style)."""
    if not header:
        return []
    inner = header.strip()[1:-1]
    names: List[str] = []
    for piece in inner.split(","):
        # last identifier in the piece is the port name ("input wire [7:0] foo")
        ids = re.findall(r"\b([a-zA-Z_]\w*)\b", re.sub(r"\[[^\]]*\]", " ", piece))
        ids = [i for i in ids if i not in _KEYWORDS]
        if ids:
            names.append(ids[-1])
    return names


def parse_rtl(rtl_dir: Path) -> Dict:
    """Parse every rtl/*.v (+ .vh): module definitions (name, file, ports),
    instantiations per module, and `define names per file."""
    rtl_dir = Path(rtl_dir)
    defs: Dict[str, dict] = {}            # module -> {file, ports}
    dupes: List[str] = []
    insts: Dict[str, List[Tuple[str, str, List[str]]]] = {}  # module -> [(child, inst, ports)]
    defines: Dict[str, str] = {}          # macro -> file
    includes: Dict[str, List[str]] = {}   # file -> included names
    texts: Dict[str, str] = {}

    for p in (sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.svh"))
              + sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))):
        raw = p.read_text(errors="replace")
        texts[p.name] = raw
        clean = _strip_comments(raw)
        for m in _DEFINE_RE.finditer(clean):
            defines.setdefault(m.group(1), p.name)
        includes[p.name] = re.findall(r'`include\s+"([^"]+)"', clean)
        for m in _MODULE_RE.finditer(clean):
            name = m.group(1)
            if name in defs:
                dupes.append(f"module `{name}` is defined in BOTH {defs[name]['file']} "
                             f"and {p.name} — delete one of them")
                continue
            defs[name] = {"file": p.name, "ports": _port_names(m.group(3) or "")}
            body_start = m.end()
            em = clean.find("endmodule", body_start)
            body = clean[body_start: em if em != -1 else len(clean)]
            found = []
            for im in _INST_RE.finditer(body):
                child, inst, conns = im.group(1), im.group(2), im.group(3)
                if child in _KEYWORDS or inst in _KEYWORDS:
                    continue
                found.append((child, inst, _NAMED_PORT_RE.findall(conns)))
            insts[name] = found
    return {"defs": defs, "dupes": dupes, "insts": insts,
            "defines": defines, "includes": includes, "texts": texts}


_DIR_KW = {"wire", "reg", "logic", "signed", "unsigned", "bit", "var"}


def _port_dirs(module_text: str) -> Dict[str, str]:
    """name -> 'input'|'output'|'inout' for one module (ANSI header or body decls).
    Robust to widths/types: a declaration runs from a direction keyword to the next
    direction keyword / ';' / ')', and every bare identifier in it that isn't a type
    keyword or a width is a port of that direction."""
    out: Dict[str, str] = {}
    # split on direction keywords, keeping them
    for m in re.finditer(r"\b(input|output|inout)\b([^;)]*?)(?=\b(?:input|output|inout)\b|[;)])",
                         _strip_comments(module_text)):
        direction, decl = m.group(1), m.group(2)
        decl = re.sub(r"\[[^\]]*\]", " ", decl)      # drop widths
        for nm in re.findall(r"\b([A-Za-z_]\w*)\b", decl):
            if nm not in _DIR_KW:
                out.setdefault(nm, direction)
    return out


def unconnected_pins(rtl_dir: Path, top: str) -> List[dict]:
    """Every OUTPUT pin left FLOATING in the top's integration — the source of the harden
    'disconnected pins' (PINMISSING) that makes a GDS a layout of a non-functional chip.
    Two classes: (a) a child instance's OUTPUT port not wired in the top's instantiation;
    (b) a top-level OUTPUT port never driven by any assign/instance/always. Returns
    [{kind, inst, module, port}] so the corrector can wire each one to a real net."""
    info = parse_rtl(rtl_dir)
    defs, texts = info["defs"], info["texts"]
    if top not in defs:
        return []
    top_text = texts.get(defs[top]["file"], "")
    tm = re.search(rf"\bmodule\s+{re.escape(top)}\b.*?\bendmodule\b", top_text, re.DOTALL)
    body = _strip_comments(tm.group(0) if tm else top_text)
    out: List[dict] = []
    # (a) child instances with unconnected OUTPUT ports
    for im in _INST_RE.finditer(body):
        child, inst, conns = im.group(1), im.group(2), im.group(3)
        if child not in defs or child in _KEYWORDS:
            continue
        connected = set(_NAMED_PORT_RE.findall(conns))
        cdirs = _port_dirs(texts.get(defs[child]["file"], ""))
        for port, d in cdirs.items():
            if d == "output" and port not in connected:
                out.append({"kind": "floating_output", "inst": inst, "module": child,
                            "port": port})
    # (b) top-level outputs never driven
    tdirs = _port_dirs(body[:body.find(";") + 1] if ";" in body else body)
    for port, d in tdirs.items():
        if d != "output":
            continue
        driven = re.search(rf"\bassign\s+{re.escape(port)}\b", body) \
            or re.search(rf"\.\w+\s*\(\s*{re.escape(port)}\b", body) \
            or re.search(rf"{re.escape(port)}\s*<=", body) \
            or re.search(rf"{re.escape(port)}\s*=", body)
        if not driven:
            out.append({"kind": "undriven_top_output", "inst": top, "module": top, "port": port})
    return out


def cone_size(rtl_dir_or_info, root: str) -> int:
    """How many modules `root` reaches transitively (itself included) — the size of its
    dependency cone. THE measure of 'how much of the design this top integrates'."""
    info = rtl_dir_or_info if isinstance(rtl_dir_or_info, dict) else parse_rtl(rtl_dir_or_info)
    defs, insts = info["defs"], info["insts"]
    seen: Set[str] = set()
    stack = [root]
    while stack:
        m = stack.pop()
        if m in seen or m not in defs:
            continue
        seen.add(m)
        stack += [c for c, _, _ in insts.get(m, []) if c in defs]
    return len(seen)


def pick_top(rtl_dir: Path) -> str:
    """Structural top: an uninstantiated module, preferring the one whose TRANSITIVE
    dependency cone covers the most of the design, with a name bonus for top/soc/chip.
    Scoring by DIRECT children was the bug that picked `riscv_core` (2 kids) over
    `chip_top` (1 kid — but its cone is the whole chip: soc → cpu + cgra + memory +
    interconnect), so lint/harden silently dropped every non-RISCV block."""
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    if not defs:
        return ""
    instantiated: Set[str] = set()
    for kids in insts.values():
        for child, _, _ in kids:
            if child in defs:
                instantiated.add(child)
    cands = [n for n in defs if n not in instantiated] or list(defs)

    def score(n: str) -> tuple:
        name_bonus = 1 if re.search(r"top|soc|chip|system", n, re.I) else 0
        kids = sum(1 for c, _, _ in insts.get(n, []) if c in defs)
        return (cone_size(info, n), name_bonus, kids)
    return max(cands, key=score)


def closure_files(rtl_dir: Path, top: str) -> Tuple[List[str], List[str]]:
    """(files needed to build `top` — module cone + their `include headers,
    orphan .v files NOT needed) — so sim never compiles stale leftovers."""
    info = parse_rtl(rtl_dir)
    defs, insts, includes = info["defs"], info["insts"], info["includes"]
    if top not in defs:
        vs = sorted(Path(rtl_dir).glob("*.v")) + sorted(Path(rtl_dir).glob("*.sv"))
        hd = sorted(Path(rtl_dir).glob("*.vh")) + sorted(Path(rtl_dir).glob("*.svh"))
        return [p.name for p in hd + vs], []
    needed_mods: Set[str] = set()
    stack = [top]
    while stack:
        m = stack.pop()
        if m in needed_mods:
            continue
        needed_mods.add(m)
        for child, _, _ in insts.get(m, []):
            if child in defs:
                stack.append(child)
    files = {defs[m]["file"] for m in needed_mods}
    # headers any needed file includes (plus all .vh — they're cheap and harmless)
    for f in list(files):
        files.update(h for h in includes.get(f, []))
    files.update(p.name for p in Path(rtl_dir).glob("*.vh"))
    files.update(p.name for p in Path(rtl_dir).glob("*.svh"))
    orphans = [p.name for p in sorted(Path(rtl_dir).glob("*.v")) + sorted(Path(rtl_dir).glob("*.sv"))
               if p.name not in files]
    ordered = ([f for f in sorted(files) if f.endswith((".vh", ".svh"))]
               + [f for f in sorted(files) if f.endswith((".v", ".sv"))])
    return [f for f in ordered if (Path(rtl_dir) / f).exists()], orphans


def audit_findings(rtl_dir: Path, top: str = "") -> List[dict]:
    """Structured cross-module audit — the single source of truth both the text report
    (static_report) and the deterministic fixer (reconcile_ports) build on. Each finding is
    a dict with a `kind`: 'dupe', 'missing_module', or 'bad_port' (a `.port(...)` connection
    that names a port the instantiated child module does not declare)."""
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    out: List[dict] = [{"kind": "dupe", "text": d} for d in info["dupes"]]
    for parent, kids in insts.items():
        pfile = defs[parent]["file"]
        for child, inst, conns in kids:
            if child not in defs:
                out.append({"kind": "missing_module", "parent": parent,
                            "parent_file": pfile, "child": child, "inst": inst})
                continue
            ports = defs[child]["ports"]
            if not ports:
                continue
            pset = set(ports)
            for c in conns:
                if c not in pset:
                    out.append({"kind": "bad_port", "parent": parent, "parent_file": pfile,
                                "child": child, "child_file": defs[child]["file"],
                                "inst": inst, "port": c, "child_ports": ports})
    return out


_DIR_SUFFIXES = ("_io", "_in", "_out", "_i", "_o")


def _has_dir(s: str) -> bool:
    return s.endswith(_DIR_SUFFIXES)


def _best_port(bad: str, ports: List[str]) -> str:
    """The UNIQUE *safe* rename for a mis-named connection `.bad(` among a child's real
    `ports`, or '' when no rename is provably safe. A wrong deterministic rename silently
    COMPILES and escapes the audit — strictly worse than leaving it for the cross-module LLM
    corrector — so this only accepts two unambiguous cases and refuses everything else:

      1. exact match apart from letter case (`.CLK` ↔ `clk`);
      2. a DIRECTIONLESS connection that gains a direction (`.a` ↔ `a_i`, `.clk` ↔ `clk_i`) —
         and only when exactly ONE child port matches.

    It deliberately NEVER toggles a present direction (`_o`↔`_i` is a different net) and does
    NO fuzzy/difflib matching (`b` vs `ab` changes meaning). Those need semantic judgement and
    are handed to the LLM corrector, which now sees both modules."""
    low = {p.lower(): p for p in ports}
    b = bad.lower()
    if b in low:                                   # case-only difference — safe
        return low[b]
    if not _has_dir(b):                            # bare name → it may just need a direction
        cand = [p for p in ports
                if p.lower() in (b + "_i", b + "_o", b + "_in", b + "_out", b + "_io")]
        if len(cand) == 1:
            return cand[0]
    return ""


def reconcile_ports(rtl_dir: Path, top: str = "") -> List[str]:
    """Deterministically repair HIGH-CONFIDENCE cross-module port-name mismatches by renaming
    the connection in the PARENT file to the child's real port (e.g. `.a(` → `.a_i(`). This
    clears the mechanical findings for free (no LLM call) so the corrector only spends the
    model on the genuine, semantic ones. SAFETY: a name is renamed only when (1) there is a
    unique confident match on the child, and (2) that name is NOT a valid port of any OTHER
    child instantiated in the same file (so we never clobber a legitimate connection).
    Returns a human-readable list of the rewrites applied."""
    rtl_dir = Path(rtl_dir)
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    changes: List[str] = []
    by_file: Dict[str, list] = {}
    for f in audit_findings(rtl_dir, top):
        if f["kind"] != "bad_port":
            continue
        repl = _best_port(f["port"], f["child_ports"])
        if repl and repl != f["port"]:
            by_file.setdefault(f["parent_file"], []).append(
                (f["port"], repl, f["child"], f["inst"], f["parent"]))
    for fname, edits in by_file.items():
        p = Path(rtl_dir) / fname
        if not p.exists():
            continue
        src = new = p.read_text()
        for old, repl, child, inst, parent in edits:
            # don't rename if `old` is a real port of some sibling child in this file
            sibling_ports = set()
            for ch, _, _ in insts.get(parent, []):
                if ch != child and ch in defs:
                    sibling_ports.update(defs[ch]["ports"])
            if old in sibling_ports:
                continue
            cand = re.sub(rf"\.{re.escape(old)}(\s*)\(", rf".{repl}\1(", new)
            if cand != new:
                new = cand
                changes.append(f"{fname}: `.{old}` → `.{repl}` (instance `{inst}` of `{child}`)")
        if new != src:
            p.write_text(new)
    return changes


def static_report(rtl_dir: Path, top: str = "") -> List[str]:
    """Cross-module audit. Each finding is ONE actionable line naming the file,
    the exact problem, and the fix — written for an LLM corrector to act on."""
    info = parse_rtl(rtl_dir)
    defines, includes, texts = info["defines"], info["includes"], info["texts"]
    problems: List[str] = []
    for f in audit_findings(rtl_dir, top):
        if f["kind"] == "dupe":
            problems.append(f["text"])
        elif f["kind"] == "missing_module":
            problems.append(
                f"{f['parent_file']}: `{f['parent']}` instantiates module `{f['child']}` "
                f"(instance `{f['inst']}`) but NO file defines `{f['child']}` — create "
                f"rtl/{f['child']}.v or fix the module name")
        elif f["kind"] == "bad_port":
            problems.append(
                f"{f['parent_file']}: connection `.{f['port']}(...)` on instance `{f['inst']}` "
                f"— but `{f['child']}` ({f['child_file']}) has no port `{f['port']}`; its real "
                f"ports are: {', '.join(f['child_ports'][:14])}. FIX: either rename this "
                f"connection to one of those real ports, OR add port `{f['port']}` to "
                f"`{f['child']}` ({f['child_file']}) and wire it; if it's a debug/formal-only "
                f"signal that nothing uses, delete the connection.")

    # SIM-ONLY constructs in RTL — legal in iverilog/verilator but FATAL in yosys ("Can't
    # resolve function name `\\$value$plusargs'"), so a multi-IP harden dies at synthesis
    # even though sim+lint passed. Flag them here (pre-sim) with the guard fix. Regions
    # already guarded for synthesis (`ifdef SYNTHESIS…`else / `ifndef SYNTHESIS…`endif)
    # are stripped before scanning so a proper guard silences the finding.
    _SIM_ONLY_RE = re.compile(
        r"\$(value\$plusargs|random|urandom\w*|fopen|fwrite|fscanf|fgets|fclose|system)\b")

    def _strip_synth_guarded(text: str) -> str:
        out, skip, depth = [], False, 0
        for ln in text.splitlines():
            d = re.match(r"\s*`(ifdef|ifndef|else|elsif|endif)\b\s*(\w*)", ln)
            if d:
                k, sym = d.group(1), d.group(2)
                if k in ("ifdef", "ifndef"):
                    depth += 1
                    if depth == 1 and sym == "SYNTHESIS":
                        skip = (k == "ifndef")      # `ifndef SYNTHESIS → sim-only region
                        continue
                elif k in ("else", "elsif") and depth == 1:
                    skip = not skip
                    continue
                elif k == "endif":
                    depth = max(depth - 1, 0)
                    if depth == 0:
                        skip = False
                        continue
            if not skip:
                out.append(ln)
        return "\n".join(out)

    for fname, raw in texts.items():
        if not fname.endswith((".v", ".sv")):
            continue
        body = _strip_synth_guarded(_strip_comments(raw))
        for m in _SIM_ONLY_RE.finditer(body):
            problems.append(
                f"{fname}: uses simulation-only `${m.group(1)}` in RTL — yosys cannot synthesize "
                "it, so hardening dies at synthesis. FIX: wrap it in `ifndef SYNTHESIS … `endif "
                "(with a synthesizable fallback under `ifdef SYNTHESIS, e.g. a for-loop init), or "
                "move it to the testbench.")
        # $readmemh with a VARIABLE path is also sim-only (a literal-string path is synthesizable)
        for m in re.finditer(r"\$readmem[hb]\s*\(\s*([A-Za-z_]\w*)", body):
            problems.append(
                f"{fname}: `$readmemh({m.group(1)}, …)` reads a VARIABLE file path — synthesizable "
                "only with a literal string path. FIX: guard it with `ifndef SYNTHESIS or use a "
                "constant path.")

    # bare macro usage: `define NAME exists in a header, file uses NAME without `
    for fname, raw in texts.items():
        if not fname.endswith(".v"):
            continue
        clean = _strip_comments(raw)
        for macro, src in defines.items():
            if re.search(rf"(?<!`)\b{re.escape(macro)}\b", clean) and src != fname:
                fix = (f"write it as `{macro}` (with the backtick)"
                       + ("" if src in includes.get(fname, [])
                          else f' and add `include "{src}" at the top of {fname}'))
                problems.append(
                    f"{fname}: uses `{macro}` as a bare identifier but it is a "
                    f"`define in {src} — {fix}")
    return problems


def check_file(path: Path, rtl_dir: Path, timeout: int = 30) -> str:
    """Compile ONE Verilog file with iverilog (-t null = no output, -i = ignore
    missing sub-modules). Returns '' when clean, else the error text. This is
    the instant feedback a generating agent gets from write_file_disk."""
    path, rtl_dir = Path(path), Path(rtl_dir)
    if path.suffix not in (".v", ".sv"):
        return ""
    cmd = ["iverilog", "-g2012", "-t", "null", "-i", f"-I{rtl_dir}", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except FileNotFoundError:
        return ""                      # no iverilog — don't block writes
    except subprocess.TimeoutExpired:
        return "(compile check timed out)"
    if proc.returncode == 0:
        # compiling clean is not enough: a $readmem of a nonexistent file only blows
        # up AT RUNTIME (all-X reads → spurious passes) — reject it here, at write time.
        return missing_data_report(path, rtl_dir)
    out = (proc.stderr or proc.stdout or "").strip()
    # keep only error lines, relative paths, capped
    lines = [ln.replace(str(path.parent) + "/", "")
             for ln in out.splitlines() if ln.strip()]
    return "\n".join(lines[:12])[:1500]


def tb_quality_report(tb_text: str, n_features: int = 0) -> Tuple[List[str], List[str]]:
    """Deterministic VERIFIABILITY check on a testbench SOURCE — returns (hard, soft).

    A `Result: PASSED` from a testbench only MEANS something if the testbench actually checks the
    design. A weak model happily writes `$display("PASSED")` with no comparison at all, or a
    verdict that is printed unconditionally — that greenlights a broken design straight into
    hardening/tape-out. HARD findings mean the tb cannot be trusted to verify anything (the sim
    gate must reject it and route to the testbench corrector); SOFT findings are audit-quality
    nudges. `n_features` (from the verification plan) enables a COVERAGE check — a comprehensive
    tb needs roughly one self-check per planned feature, not one lucky path. Checked on source
    text (no simulation needed), so it runs before every sim."""
    t = _strip_comments(tb_text or "")
    hard: List[str] = []
    soft: List[str] = []
    if "$finish" not in t:
        hard.append("no `$finish` — the simulation can hang forever instead of ending with a verdict")
    if not re.search(r"===|!==|==|!=|<=|>=|[<>]", t):
        hard.append("no comparison against an expected value — the testbench is not self-checking")
    has_pass = bool(re.search(r"\bPASSED\b", t))
    has_fail = bool(re.search(r"\bFAILED\b", t))
    if not has_pass:
        hard.append('never prints a "Result: PASSED" verdict — nothing signals success')
    if has_pass and not has_fail:
        hard.append("prints PASSED but has no FAILED branch — the verdict is UNCONDITIONAL "
                    "(it will 'pass' even when the design is wrong)")
    # a self-checking tb prints PASSED only under a condition, not as a bare top-level statement
    if has_pass and not re.search(r"\bif\b|\?|\berror", t, re.I):
        hard.append("prints PASSED but has no `if`/error-count guarding it — the pass is not "
                    "derived from any check")
    # HARD (user rule: 'testbench harus verifiable banget'): every case must be AUDITABLE
    # — a PASS that can't be traced to an expected-vs-actual pair proves nothing — and a
    # hung DUT must FAIL by watchdog, never stall the whole verify loop.
    if not re.search(r"expected", t, re.I):
        hard.append("does not label an EXPECTED value per case — print `expected=.. actual=..` "
                    "on every check so each PASS is auditable at tape-out")
    elif not re.search(r"\bin\s*=", t):
        soft.append("case lines don't show the INPUTS — print `in=<stimulus>` on each case so the "
                    "reader sees what drove every expected/actual pair")
    if not (re.search(r"#\s*\d{4,}", t) or re.search(r"timeout", t, re.I)):
        hard.append("no timeout watchdog — add `initial begin #100000; $display(\"Result: FAILED "
                    "(timeout)\"); $finish; end` so a hung DUT FAILS instead of hanging")
    # clocked tb without a cycle counter — latency is part of verification
    if re.search(r"posedge\s+clk|always\s*#\s*\d+\s+clk", t) and not re.search(r"\bcycles?\b", t, re.I):
        soft.append("no cycle counter — add `integer cycles; always @(posedge clk) cycles=cycles+1;` "
                    "and print `CYCLES: total=%0d` so latency is measured, not just correctness")
    # COVERAGE: a comprehensive tb has ~one self-check per planned feature. Count expected-vs-actual
    # checks (an `expected` label, a `-> PASS/FAIL` print, or a check-task call). Grossly incomplete
    # (< half the features) is HARD — that's a "one lucky path" tb; a small shortfall is SOFT.
    if n_features > 0:
        checks = max(len(re.findall(r"expected", t, re.I)),
                     len(re.findall(r"->\s*(?:PASS|FAIL)", t)),
                     len(re.findall(r"\bcheck\w*\s*\(", t)))
        if checks and checks < (n_features + 1) // 2:
            hard.append(f"covers only ~{checks} of {n_features} planned features — not comprehensive; "
                        "add a self-check (expected vs actual) for EACH feature in the plan")
        elif checks < n_features:
            soft.append(f"covers ~{checks} of {n_features} planned features — add the missing ones "
                        "so every feature is verified, not just some")
    return hard, soft


def check_tb(tb_path: Path, rtl_dir: Path, timeout: int = 60) -> str:
    """Compile a TESTBENCH the way it will actually be simulated: TOGETHER with the real
    DUT modules it instantiates (its dependency cone), NOT alone.

    Why this exists: check_file() compiles one file with `-i` (ignore missing sub-modules),
    which STUBS OUT the DUT. A self-checking testbench that reaches into the design with a
    hierarchical reference (`dut.u_rf.regs[9]`, `dut.state`, …) then fails to bind against
    the empty stub — iverilog prints `Unable to bind wire/reg/memory dut.u_rf.regs[...]`.
    That is a PHANTOM error: the very same testbench compiles cleanly once the real DUT is
    present. A corrector loop can never win against it, so tb compile-checks MUST bring the
    DUT along. Returns '' when clean, else the error text (paths stripped, capped)."""
    tb_path, rtl_dir = Path(tb_path), Path(rtl_dir)
    if tb_path.suffix not in (".v", ".sv"):
        return ""
    info = parse_rtl(rtl_dir)
    tb_stem = tb_path.stem
    body = _strip_comments(tb_path.read_text(errors="replace"))
    # every design module the testbench names → pull each one's closure so the whole
    # hierarchy under the DUT is present for elaboration (hierarchical refs then bind).
    needed: Set[str] = set()
    for mod in info["defs"]:
        if mod != tb_stem and re.search(rf"\b{re.escape(mod)}\b", body):
            fs, _ = closure_files(rtl_dir, mod)
            needed.update(fs)
    if not needed:                          # tb references no known module → syntax-only check
        return check_file(tb_path, rtl_dir)
    vfiles = [str(rtl_dir / f) for f in sorted(needed)
              if f.endswith((".v", ".sv")) and (rtl_dir / f).exists()]
    cmd = ["iverilog", "-g2012", "-t", "null", f"-I{rtl_dir}",
           "-s", tb_stem, str(tb_path), *vfiles]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except FileNotFoundError:
        return ""                           # no iverilog — don't block
    except subprocess.TimeoutExpired:
        return "(testbench compile check timed out)"
    if proc.returncode == 0:
        return ""
    out = (proc.stderr or proc.stdout or "").strip()
    lines = [ln.replace(str(rtl_dir) + "/", "").replace(str(tb_path.parent) + "/", "")
             for ln in out.splitlines() if ln.strip()]
    return "\n".join(lines[:14])[:1600]


# ---------------------------------------------------------------------------
# $readmemh/$readmemb DATA FILES — the CWD trap this kills: vvp runs with
# cwd=sim/, but agents write testbenches that load "tb/golden/x.mask" (design-
# root-relative) or "weights.mem" (bare name, file lives in rtl/). $readmemh
# then fails AT RUNTIME ("Unable to open ... for reading"), the memory stays
# all-X/0, and both the golden model and the DUT compute on zeros — spurious
# expected=0 actual=0 PASS lines that hide the real test. Three defenses:
#   readmem_refs()        — find every string-literal $readmem path in a source.
#   find_data_file()      — resolve a ref against the design dir (exact relative
#                           path from every root, then basename rescue).
#   stage_readmem_files() — copy each resolved file into sim/ AT THE PATH THE
#                           SOURCE USES, so it opens from the sim CWD no matter
#                           how the tb spelled it; unresolvable refs are HARD
#                           errors reported BEFORE the sim ever runs.
# check_file()/check_tb() also call missing_data_report(), so a tb that loads a
# nonexistent file is rejected AT WRITE TIME with instructions, not discovered
# three stages later as a mysterious all-zeros pass.
# ---------------------------------------------------------------------------
_READMEM_RE = re.compile(r'\$readmem[hb]\s*\(\s*"([^"]+)"', re.I)


def readmem_refs(text: str) -> List[str]:
    """Every string-literal $readmemh/$readmemb path in a Verilog source (comments
    stripped, order preserved, de-duplicated). Non-literal paths (parameters/regs)
    can't be resolved statically and are ignored."""
    seen: List[str] = []
    for ref in _READMEM_RE.findall(_strip_comments(text or "")):
        if ref not in seen:
            seen.append(ref)
    return seen


def find_data_file(ref: str, design_dir: Path) -> "Path | None":
    """Resolve one $readmem path literal to the real file on disk, or None.
    Tries the ref as-is from every design root, then rescues a bare/mis-rooted name by
    basename search — the agent that wrote `$readmemh(\"weights.mem\")` while the file
    sits at rtl/weights.mem. DURABLE roots (design/, tb/, rtl/) are preferred over sim/
    — sim/ holds throwaway staging copies rewritten every iteration, and harden's
    absolutize_readmem must pin synthesis to the original, not a copy that may vanish."""
    design_dir = Path(design_dir)
    rp = Path(ref)
    if rp.is_absolute():
        return rp if rp.exists() else None
    for root in (design_dir, design_dir / "tb", design_dir / "rtl", design_dir / "sim"):
        if (root / rp).is_file():
            return root / rp
    for root in (design_dir / "tb", design_dir / "rtl", design_dir / "sim"):
        if root.is_dir():
            hits = sorted(p for p in root.rglob(rp.name) if p.is_file())
            if hits:
                return hits[0]
    return None


def stage_readmem_files(sim_dir: Path, src_files: List[Path],
                        design_dir: Path) -> Tuple[List[str], List[str]]:
    """Make every $readmem path in the given Verilog sources resolvable from the
    sim CWD (vvp runs with cwd=sim_dir): copy each resolved data file to
    sim_dir/<ref-as-written> so the literal path in the source just works.
    Returns (staged notes, missing errors). A missing entry means NO file on
    disk matches the ref — running the sim would read all-X and produce
    meaningless passes, so callers must FAIL FAST and route the message to the
    corrector instead of simulating."""
    sim_dir, design_dir = Path(sim_dir), Path(design_dir)
    staged: List[str] = []
    missing: List[str] = []
    for sf in src_files:
        sf = Path(sf)
        try:
            text = sf.read_text(errors="replace")
        except OSError:
            continue
        for ref in readmem_refs(text):
            if Path(ref).is_absolute():
                if not Path(ref).exists():
                    missing.append(_missing_msg(sf.name, ref))
                continue
            src = find_data_file(ref, design_dir)
            if src is None:
                missing.append(_missing_msg(sf.name, ref))
                continue
            dst = sim_dir / ref
            try:
                if src.resolve() != dst.resolve():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    staged.append(f"{ref} ← {src.relative_to(design_dir)}"
                                  if src.is_relative_to(design_dir) else ref)
            except OSError as e:
                missing.append(f"{sf.name}: could not stage \"{ref}\" for the sim ({e})")
    return staged, missing


def _missing_msg(src_name: str, ref: str) -> str:
    return (f"{src_name}: $readmem loads \"{ref}\" but NO such data file exists anywhere in "
            "the design dir — the sim would read all-X/0 and every check becomes meaningless. "
            "Either generate the data INLINE in Verilog (initial block / task, no file I/O — "
            "preferred), or FIRST create the file (write_file / run_python) at a design-root-"
            "relative path like tb/golden/case1.mask or rtl/weights.mem and reference it by "
            "that exact path.")


def absolutize_readmem(path: Path, design_dir: Path) -> List[str]:
    """Rewrite literal $readmem paths in a STAGED COPY of an RTL file to ABSOLUTE paths.
    Yosys executes $readmemh at synthesis time too (ROM/weights inference) and resolves
    the path from ITS OWN CWD — the LibreLane step dir, not the design dir — so a
    relative "rtl/weights.mem" silently zero-fills the ROM and the whole datapath
    const-folds away (the 'optimized to 34 tie cells' dead-chip failure). An absolute
    path resolves from anywhere. Call this ONLY on throwaway staging copies (chip/src/,
    macros/*/src/), never on the user's rtl/. Returns one note per rewrite."""
    path = Path(path)
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    notes: List[str] = []

    def _sub(m: "re.Match[str]") -> str:
        ref = m.group(2)
        if Path(ref).is_absolute():
            return m.group(0)
        src = find_data_file(ref, design_dir)
        if src is None:
            return m.group(0)          # missing files are the sim gates' job, not ours
        notes.append(f"{path.name}: \"{ref}\" → {src}")
        return m.group(1) + str(src.resolve()) + m.group(3)

    new = re.sub(r'(\$readmem[hb]\s*\(\s*")([^"]+)(")', _sub, text, flags=re.I)
    if notes:
        path.write_text(new)
    return notes


def missing_data_report(path: Path, rtl_dir: Path) -> str:
    """Write-time gate: '' when every $readmem ref in this file resolves to a real
    file, else one actionable error per missing ref (same contract as check_file)."""
    path = Path(path)
    try:
        refs = readmem_refs(path.read_text(errors="replace"))
    except OSError:
        return ""
    design_dir = Path(rtl_dir).parent
    return "\n".join(_missing_msg(path.name, r) for r in refs
                     if find_data_file(r, design_dir) is None)


_GUARD_RE = re.compile(r"^\s*`(ifndef|ifdef|endif|else)\b|^\s*`define\s+\w*(_S?VH|_H)\b"
                       r"|^\s*`define\s+GARUDA_\w+", re.I)


def normalize_headers(rtl_dir: Path) -> List[str]:
    """Collapse EVERY header (.vh/.svh) in rtl/ into ONE canonical header, so the design can
    never carry two overlapping define files.

    The two-header mess this fixes: the generator emits the shared `define`s inline at the top
    of its blob AND as a separate `riscv_defines.vh`; the mechanical splitter then bundles that
    leading content into a SECOND header (`shared_header.vh`) that duplicates every macro and
    even `` `include``s itself. iverilog tolerates it (the guards de-dup), but it is exactly the
    'redundancy error' foot-gun the user hit and it makes the design unreadable.

    This pass: (1) gathers every `` `define`` across all headers, first definition wins (dedup by
    macro name, guard defines skipped); (2) writes ONE guarded canonical header; (3) rewrites
    every module so it `` `include``s ONLY that header; (4) deletes the other headers. Returns a
    human-readable list of what changed ([] if there was 0 or 1 header and nothing to do)."""
    rtl_dir = Path(rtl_dir)
    hdrs = sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.svh"))
    if not hdrs:
        return []

    defines: Dict[str, str] = {}          # macro name -> full `define line (first wins)
    order: List[str] = []
    timescale = ""
    extra: List[str] = []                 # substantive non-define lines (parameter/typedef/…)
    extra_seen: Set[str] = set()
    for h in hdrs:
        for raw in h.read_text(errors="replace").splitlines():
            s = raw.strip()
            if not s or s.startswith(("//", "*", "/*")) or s.endswith("*/") and s.startswith("*"):
                continue
            if re.match(r"\s*`include\b", s):            # drop nested/self includes
                continue
            if _GUARD_RE.match(s):                       # include-guard lines — we add our own
                continue
            m = re.match(r"`define\s+(\w+)", s)
            if m:
                if m.group(1) not in defines:
                    defines[m.group(1)] = raw.rstrip()
                    order.append(m.group(1))
                continue
            if s.startswith("`timescale"):
                timescale = timescale or raw.rstrip()
                continue
            if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
                continue
            if s not in extra_seen:                      # parameters/typedefs/packages, deduped
                extra_seen.add(s)
                extra.append(raw.rstrip())

    # canonical header name: reuse a "defines"/"header" one if present, else the first header.
    pref = ([h for h in hdrs if re.search(r"defin|param", h.name, re.I)]
            + [h for h in hdrs if re.search(r"header|shared|pkg|common", h.name, re.I)]
            + hdrs)
    canonical = pref[0].name
    guard = "GARUDA_" + re.sub(r"\W", "_", canonical).upper()

    lines = [f"`ifndef {guard}", f"`define {guard}", ""]
    if timescale:
        lines += [timescale, ""]
    lines += ["// Shared parameters / opcodes for the whole design (single source of truth)."]
    lines += [defines[n] for n in order]
    if extra:
        lines += [""] + extra
    lines += ["", f"`endif // {guard}", ""]
    new_header = "\n".join(lines)

    changes: List[str] = []
    (rtl_dir / canonical).write_text(new_header)
    changes.append(f"merged {len(hdrs)} header(s) → single `{canonical}` "
                   f"({len(order)} macro(s), deduped)")
    for h in hdrs:                                        # delete the redundant ones
        if h.name != canonical:
            h.unlink()
            changes.append(f"deleted redundant header `{h.name}`")

    # re-point every module include to the one canonical header (exactly one include).
    inc_re = re.compile(r'^[ \t]*`include\s+"[^"]+\.(?:vh|svh)"[ \t]*\r?\n?', re.M)
    macro_use = re.compile(r"`(" + "|".join(re.escape(n) for n in order) + r")\b") if order else None
    for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        src = p.read_text(errors="replace")
        had_inc = bool(inc_re.search(src))
        stripped = inc_re.sub("", src)
        uses_macro = bool(macro_use and macro_use.search(_strip_comments(stripped)))
        if had_inc or uses_macro:
            new = f'`include "{canonical}"\n' + stripped.lstrip("\n")
            if new != src:
                p.write_text(new)
    return changes


def full_report(rtl_dir: Path, top: str = "", only: Set[str] | None = None) -> str:
    """Everything wrong with the design as one actionable digest ('' = clean):
    per-file compile errors + the cross-module static audit. `only` limits the
    report to that set of file names (e.g. the simulation closure), so stale
    orphan files can't block the build."""
    rtl_dir = Path(rtl_dir)
    parts: List[str] = []
    for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        if only is not None and p.name not in only:
            continue
        err = check_file(p, rtl_dir)
        if err:
            parts.append(f"--- {p.name} (single-file compile) ---\n{err}")
    audit = static_report(rtl_dir, top)
    if only is not None:
        audit = [a for a in audit if a.split(":", 1)[0] in only]
    if audit:
        parts.append("--- cross-module audit ---\n" + "\n".join(audit[:25]))
    return "\n\n".join(parts)


# SystemVerilog constructs that iverilog -g2012 / Verilator accept (so sim + lint pass) but the
# plain Verilog-2005 yosys frontend REJECTS with "syntax error, unexpected '['" — the harden step
# then dies (LibreLane rc=2) with no GDS, even though simulation passed. Routing such RTL through
# USE_SLANG (yosys-slang) parses it correctly. We detect by CONTENT, not file extension, because
# the generator emits SystemVerilog inside .v files.
_SV_HINT_RE = re.compile(
    r"\b(logic|bit|always_ff|always_comb|always_latch|typedef|interface|endinterface|"
    r"modport|package|endpackage|priority|unique|\.\*)\b|\bstruct\s+packed\b|\bunion\s+packed\b")
# An UNPACKED-array port: a dimension AFTER the signal name, e.g. `input [31:0] cfg_word [0:N-1]`.
# (A packed-only port `input [31:0] data,` has its `[` BEFORE the name and does NOT match.)
_UNPACKED_PORT_RE = re.compile(
    r"\b(?:input|output|inout)\b[^;)\n]*?\b[A-Za-z_]\w*\s*\[[^\]]*\]\s*[,;)\n]")


def needs_slang(rtl_dir: Path) -> bool:
    """True when the RTL uses SystemVerilog constructs the Verilog-2005 yosys frontend can't
    parse (unpacked-array ports, `logic`, `always_ff`, typedefs/interfaces/packed structs). Such
    RTL passes Verilator sim/lint but makes plain yosys die at synthesis ("syntax error,
    unexpected '['") so LibreLane returns rc=2 with no GDS. The harden config should set
    USE_SLANG=true whenever this returns True — even for a design whose files are all named .v —
    so it routes through yosys-slang and reaches GDSII. Checked by file CONTENT, not extension."""
    rtl_dir = Path(rtl_dir)
    files = (list(rtl_dir.glob("*.sv")) + list(rtl_dir.glob("*.svh"))
             + list(rtl_dir.glob("*.v")) + list(rtl_dir.glob("*.vh")))
    if any(p.suffix in (".sv", ".svh") for p in files):
        return True
    for p in files:
        try:
            t = _strip_comments(p.read_text(errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        if _UNPACKED_PORT_RE.search(t) or _SV_HINT_RE.search(t):
            return True
    return False
