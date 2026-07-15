"""Chip-Orchestra Deep Agents — every LLM stage node is a Recursive-Language-Model
style (RLM) deep agent, ported from GarudaChip and driven by the configured
local model (Ollama, e.g. qwen3.5:9b).

The MIT "Recursive Language Models" idea (arXiv:2512.24601) applied here:
treat the big stuff (reference designs, error logs, the existing RTL) as an
*environment on disk* — NOT as one giant prompt. The root agent keeps its own
window SMALL: it PEEKS at slices (`read_file_disk` with line ranges, `grep_files`)
and DELEGATES focused sub-tasks to fresh sub-LLM calls (`llm_query`) or full
sub-agents (the built-in `task` tool). It builds the answer up in files, then
returns it. This is why a 9B local model can handle large designs: it never has
to hold everything at once.

The model is ALWAYS get_chat_model() (the configured provider). deepagents'
Anthropic default is never used because we pass `model=` explicitly.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

from langchain_core.tools import tool

from llm import get_chat_model

PITFALLS = (
    "Write synthesizable Verilog-2001. Avoid these classic mistakes: "
    "(1) to reset an unpacked array `reg [W-1:0] mem [0:N-1]` use a for-loop, never "
    "`mem <= 0` or `mem <= {N{...}}`; (2) replication needs double braces `{4{8'd0}}`, "
    "never `4{8'd0}`; (3) one driver per signal — never assign a reg from two `always` "
    "blocks; (4) a signal assigned in `always` must be `reg`/`output reg`, declared once."
)

# RLM-style operating contract shared by every deep-agent node. Each pipeline
# node ALSO gets a specific goal (the user message); this is the standing
# behaviour: keep context small, peek, delegate, build up in files, verify.
INSTRUCTIONS = f"""You are a Chip-Orchestra Verilog/SoC engineer agent operating as a
Recursive Language Model (RLM): you keep your OWN context small and treat large
inputs as an environment on disk.

You manage REAL files for one chip design with your file tools — `list_files`,
`read_file_disk` (reads a SLICE: pass start_line/max_lines), `write_file_disk`,
`delete_file_disk`, and `grep_files` (regex-probe across files). RTL lives under
`rtl/`, testbenches under `tb/`, offloaded context under `context/`.

How to work (RLM loop):
0. STATE FIRST. If `context/state.md` exists, read it before anything else — it is the
   RUN JOURNAL: what has been built, which IPs passed/failed unit verify, and what the
   user asked/steered. Interpret your task against that state; never redo what it
   records as done, never contradict what the user asked there.
1. PEEK, don't swallow. For anything big (references, error logs, existing RTL),
   `grep_files` for the relevant lines or `read_file_disk` a slice — never assume
   you must read a whole file to act.
2. DELEGATE focused sub-tasks. Use `llm_query(prompt)` to summarize/extract/classify
   a slice, or to draft ONE small module — give it a self-contained prompt with just
   the slice it needs, so YOUR window stays small. Use the `task` tool for a heavier
   sub-job. Do NOT over-delegate: batch related work into one call.
3. RECURSE IN CODE when the work is repetitive over many pieces (many files, many
   chunks of one big file): inside `run_python` a function `llm(prompt)` is available —
   write a SHORT script that LOOPS over the pieces, calls `llm(...)` once per piece,
   and collects/writes the results to a context/ file you then read. A code loop covers
   EVERY piece deterministically — better than reasoning turn-by-turn. Example:
   `from pathlib import Path` then
   `notes = [llm('List the ports+role of this Verilog, tersely: ' + p.read_text()[:4000])
   for p in sorted(Path('context/anchor').rglob('*.v'))[:8]]` then write them to
   `context/anchor_digest.md`.
4. BUILD UP in files. Write intermediate and final RTL to `rtl/<module>.v` with
   `write_file_disk` instead of holding it all in your reply.
5. Use `write_todos` to plan multi-step work and track progress.
6. PYTHON IS OTHERWISE A DATA TOOL — NOT a deliverable. Most designs (CPU, ALU, FSM,
   regfile, datapath, controller) need NO Python at all; write them straight as RTL.
   Reach for `run_python` ONLY when the hardware is genuinely DATA-DRIVEN and the data
   needs real computation:
     • LINEARIZE/quantize a math function into a LUT (relu, softmax, sigmoid, sin/cos,
       reciprocal) — numpy;
     • TRAIN or derive NN weights/filter taps to bake into the chip — numpy/torch;
     • a C/C++/C reference KERNEL to cross-check a low-level datapath against.
   When you do, use `run_python` to EMIT the result — QUANTIZE to the right format
   (signed/unsigned int, or Qm.n fixed-point) and WRITE a `rtl/<name>.mem` loaded by
   `$readmemh`/`$readmemb`, or print constants to bake into the RTL. The Python is a
   throw-away generator: do NOT leave a `*.py` script in `rtl/` as part of the design.
   (`run_python` is also fine for reading an attached PDF/image with pypdf/pillow.)
   If the math is just arithmetic the RTL already does, skip Python entirely.
7. VERIFY before finishing — re-read what you wrote and check it against the rules.
- {PITFALLS}
- Before editing a file, read it first. After writing, confirm the file path.
"""


# Per-file last compile error during a write (path -> (error, broken_content)), so when a
# file goes broken→clean we can persist the error→fix lesson. Module-level so it survives
# across write_file_disk calls within a generation step.
_LAST_WRITE_ERR: dict = {}


def _save_gen_fix_lesson(err: str, broken: str, fixed: str, design: str) -> None:
    """Persist a fix made DURING generation to the lesson store, with a stable
    id by error signature so it dedupes. This is what makes EVERY problem solved
    while working get saved — not just repair-stage fixes."""
    try:
        from lessons import error_signature, remember_fix
        remember_fix(error_signature(err), design=design, broken=broken[:1200], fixed=fixed[:1600])
    except Exception:  # noqa: BLE001
        pass


def make_fs_tools(base_dir: str | Path, on_clean_write=None) -> List:
    """Real on-disk file tools, sandboxed to `base_dir` (the task workspace).
    Reads are SLICED (RLM 'peek') and there is a regex `grep_files` so an agent can
    probe a large context without loading it whole — the key to keeping the local
    model's window small. `on_clean_write(relpath) -> str` (optional) fires the moment a
    NON-testbench Verilog file passes its compile check; whatever it returns is appended
    to the tool result so the agent sees the verdict."""
    base = Path(base_dir).resolve()

    def _resolve(path: str) -> Path:
        p = (base / (path or "")).resolve()
        if p != base and base not in p.parents:
            raise ValueError(f"path '{path}' escapes the design directory")
        return p

    @tool
    def list_files(subdir: str = "") -> str:
        """List files under the design directory. Optionally pass a subdir like 'rtl' or 'tb'."""
        d = _resolve(subdir)
        if not d.exists():
            return f"(no such path: {subdir or '.'})"
        if d.is_file():
            return str(d.relative_to(base))
        files = [str(p.relative_to(base)) for p in sorted(d.rglob("*"))
                 if p.is_file() and "chip/runs" not in str(p.relative_to(base))]
        return "\n".join(files) or "(empty)"

    @tool
    def read_file_disk(path: str, start_line: int = 1, max_lines: int = 250) -> str:
        """Read a SLICE of a text file under the design dir, e.g. 'rtl/cpu.v'.
        Returns a header (total lines/chars) then lines [start_line, start_line+max_lines).
        PEEK at big files in slices instead of reading them whole — keeps context small."""
        p = _resolve(path)
        if not p.exists() or not p.is_file():
            return f"(not found: {path})"
        text = p.read_text(errors="replace")
        lines = text.splitlines()
        n = len(lines)
        start = max(1, int(start_line))
        end = min(n, start - 1 + max(1, int(max_lines)))
        body = "\n".join(lines[start - 1:end]) if n else ""
        more = "" if end >= n else f"\n… ({n - end} more lines — read from line {end + 1} to continue)"
        return (f"# {path} — {n} lines, {len(text)} chars; showing {start}-{end}\n{body}{more}")[:20000]

    @tool
    def grep_files(pattern: str, subdir: str = "") -> str:
        """Regex-search the design files (optionally within a subdir like 'rtl' or
        'context'). Returns up to 60 matching 'path:line: text' rows. Use this to
        PROBE a large context (references, error logs, RTL) instead of reading whole
        files — the fastest way to find the lines you actually need."""
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"(bad regex: {e})"
        d = _resolve(subdir)
        roots = [d] if d.exists() else []
        hits: List[str] = []
        for root in roots:
            paths = [root] if root.is_file() else sorted(
                p for p in root.rglob("*")
                if p.is_file() and "chip/runs" not in str(p) and p.suffix in
                (".v", ".vh", ".sv", ".svh", ".md", ".log", ".txt", ".json"))
            for p in paths:
                try:
                    for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                        if rx.search(line):
                            hits.append(f"{p.relative_to(base)}:{i}: {line.strip()[:160]}")
                            if len(hits) >= 60:
                                return "\n".join(hits) + "\n… (truncated at 60 matches)"
                except Exception:  # noqa: BLE001
                    continue
        return "\n".join(hits) or f"(no matches for /{pattern}/)"

    @tool
    def write_file_disk(path: str, content: str) -> str:
        """Create or OVERWRITE a file under the design dir, e.g. 'rtl/alu.v'. Use this to
        save new or updated Verilog. Verilog files are AUTO-REPAIRED (obvious syntax tics)
        and COMPILE-CHECKED on write: if the result says COMPILE ERRORS, fix the file and
        write it again before moving on."""
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fixnote = ""
        if p.suffix in (".v", ".sv", ".vh"):
            try:
                from verilog_check import autofix_text
                content, notes = autofix_text(content)
                if notes:
                    fixnote = " · auto-repaired: " + "; ".join(notes)
            except Exception:  # noqa: BLE001
                pass
        p.write_text(content)
        note = f"wrote {path} ({len(content)} bytes){fixnote}"
        # Instant feedback loop: a syntax/elaboration error surfaces in THIS tool result,
        # so the agent fixes the file now — not 10 modules later at simulation time.
        if p.suffix in (".v", ".sv"):
            # A testbench is compiled WITH its DUT (check_tb) so a self-checking hierarchical
            # reference (`dut.u_rf.regs[9]`) binds; a plain module uses check_file (-i stubs
            # missing sub-modules). Using check_file on a tb would report a phantom
            # "Unable to bind" from the stubbed-out DUT that no rewrite can clear.
            try:
                from verilog_check import check_file, check_tb
                is_tb = "tb/" in path.replace("\\", "/") or "_tb." in p.name
                err = check_tb(p, base / "rtl") if is_tb else check_file(p, base / "rtl")
                if err:
                    _LAST_WRITE_ERR[str(p)] = (err, content)   # remember for the fix-lesson
                    return (f"{note}\nCOMPILE ERRORS — fix this file and write it again "
                            f"NOW (do not move to the next module):\n{err}")
                # broken→clean during GENERATION = a real fix → save the lesson to the
                # lesson store so the same mistake isn't repeated next run.
                prev = _LAST_WRITE_ERR.pop(str(p), None)
                if prev:
                    _save_gen_fix_lesson(prev[0], prev[1], content, base.name)
                extra = ""
                if on_clean_write and not is_tb:
                    try:                     # per-IP verify hook (generation step)
                        extra = on_clean_write(path) or ""
                    except Exception:  # noqa: BLE001
                        extra = ""
                return f"{note} — compile check clean ✓{extra}"
            except Exception:  # noqa: BLE001
                pass
        return note

    @tool
    def delete_file_disk(path: str) -> str:
        """Delete a file under the design dir, e.g. 'rtl/shared_header.vh'."""
        p = _resolve(path)
        if p.exists() and p.is_file():
            p.unlink()
            return f"deleted {path}"
        return f"(not found: {path})"

    @tool
    def rename_file_disk(src: str, dst: str) -> str:
        """Rename/move a file under the design dir, e.g. rename 'rtl/sram_1kb.v' to
        'rtl/sram_256b.v' after shrinking it, or 'tb/old_tb.v' to 'tb/top_module_tb.v'.
        Use this (not delete+write) when a file's identity changes so history stays clean.
        Remember to update every `include and instantiation that referenced the old name."""
        sp, dp = _resolve(src), _resolve(dst)
        if not sp.exists() or not sp.is_file():
            return f"(not found: {src})"
        dp.parent.mkdir(parents=True, exist_ok=True)
        sp.rename(dp)
        return f"renamed {src} → {dst}"

    return [list_files, read_file_disk, grep_files, write_file_disk, delete_file_disk,
            rename_file_disk]


def make_rlm_tools(temperature: float = 0.2, model=None) -> List:
    """The RLM recursion primitive: `llm_query`, a single fresh local-LLM call the
    root agent uses to DELEGATE a focused sub-task (summarize/extract/classify a
    slice, or draft one small module) so its own context stays small. Pairs with the
    built-in `task` tool (heavier sub-agent delegation) that deepagents always adds."""

    @tool
    def llm_query(prompt: str) -> str:
        """Delegate a focused sub-task to a fresh local LLM call and return its answer.
        Give a SELF-CONTAINED prompt (include the exact slice of context to process):
        e.g. 'Summarize the ports of this module: <code>' or 'Write an 8-bit adder
        module named add8'. Use this to keep YOUR own context small. Batch related
        work into one call — do not call it per line."""
        m = model or get_chat_model(temperature=temperature)
        try:
            out = m.invoke(prompt)
            text = getattr(out, "content", None)
            if not text:
                text = str(out)
        except Exception as e:  # noqa: BLE001
            return f"(llm_query failed: {e})"
        return text[:6000]

    return [llm_query]


def make_python_tools(base_dir: str | Path, timeout: int = 0) -> List:
    """A real Python sandbox for the agent: `run_python` (execute a snippet, capture
    output) and `pip_install` (fetch libraries on demand). This lets a node PROTOTYPE
    in Python before writing Verilog — build/quantize LUTs (relu, softmax, sin) and
    filter/NN coefficients with numpy/torch, test a paper's algorithm, or parse an
    attached PDF/image — and drop the results (e.g. a `.mem` file) next to the RTL.
    The snippet also gets `llm(prompt)` — a fresh local-LLM call usable FROM CODE, the
    RLM recursion primitive: orchestration code loops over pieces of context and fans
    sub-queries out deterministically. Scripts run with the current interpreter,
    cwd = the design dir, with a timeout so a runaway can't hang the service."""
    base = Path(base_dir).resolve()
    timeout = timeout or int(os.getenv("GARUDA_PY_TIMEOUT_S", "600"))

    # PERSISTENT dependency dir on the shared workspace volume: pip_install
    # targets it and run_python puts it on PYTHONPATH, so packages the agents
    # install survive container restarts/rebuilds and are shared across tasks.
    pydeps = Path(os.getenv("AGENT_PYDEPS_DIR")
                  or Path(os.getenv("AGENT_ARTIFACT_ROOT",
                                    os.getenv("WORKSPACE_ROOT",
                                              "/tmp/chip-orchestra/workspaces"))) / ".pydeps")

    def _pydeps_env() -> dict:
        env = dict(os.environ)
        if pydeps.is_dir():
            env["PYTHONPATH"] = f"{pydeps}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
        return env

    # `llm()` available INSIDE the snippet: a direct Ollama /api/chat call (no imports from
    # this package needed in the subprocess). Model = the run's active pick, passed via env.
    _LLM_HELPER = (
        "def llm(prompt, temperature=0.2):\n"
        "    \"\"\"One fresh local-LLM call — the RLM recursion primitive, callable from code.\n"
        "    Loop over chunks/files and call this per piece; collect the results.\"\"\"\n"
        "    import json as _j, os as _o, urllib.request as _u\n"
        "    _b = _o.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')\n"
        "    _m = _o.environ.get('GARUDA_LLM_MODEL') or _o.environ.get('OLLAMA_MODEL', 'qwen3.5:9b')\n"
        "    _body = {'model': _m, 'messages': [{'role': 'user', 'content': str(prompt)[:24000]}],\n"
        "             'stream': False, 'think': False, 'options': {'temperature': temperature}}\n"
        "    _rq = _u.Request(_b + '/api/chat', _j.dumps(_body).encode(),\n"
        "                     {'Content-Type': 'application/json'})\n"
        "    _r = _j.loads(_u.urlopen(_rq, timeout=600).read())\n"
        "    try:  # token accounting — folded into the stage's token note\n"
        "        with open('context/tokens.jsonl', 'a') as _f:\n"
        "            _f.write(_j.dumps({'in': _r.get('prompt_eval_count', 0),\n"
        "                               'out': _r.get('eval_count', 0)}) + chr(10))\n"
        "    except Exception:\n"
        "        pass\n"
        "    return _r['message']['content']\n"
    )

    @tool
    def run_python(code: str) -> str:
        """Run a Python snippet in the design directory and return its stdout/stderr.
        Use it to COMPUTE data for hardware before writing Verilog: build a LUT
        (relu/softmax/sigmoid/sin), filter taps, or NN weights with numpy/torch,
        QUANTIZE to int or Qm.n fixed-point, and WRITE them to a file —
        `open('rtl/relu_lut.mem','w')` of hex/bin lines that Verilog loads with
        `$readmemh`/`$readmemb` — or just print the constants to bake into the RTL.
        A function `llm(prompt) -> str` is predefined in the snippet: use it to RECURSE
        over big context — loop over files/chunks, call llm() per piece, collect and
        write the results to a context/ file (deterministic coverage via a code loop).
        Also good for testing an algorithm/paper concept, or reading an attached
        PDF/image (pip_install pypdf / pillow first). The working dir is the design
        dir, so relative paths like 'rtl/...' resolve there. matplotlib is forced to
        the headless 'Agg' backend — savefig to a file, never show(). Keep prints
        SMALL: you only get back the last ~6000 characters."""
        work = base / "work"
        work.mkdir(parents=True, exist_ok=True)
        script = work / "_snippet.py"
        # PERSIST every executed snippet under sw/scripts/ so the generated Python (image
        # preprocessing, golden models, LUT/weight generators) is a KEPT deliverable, not
        # throwaway.
        try:
            keep = base / "sw" / "scripts"
            keep.mkdir(parents=True, exist_ok=True)
            n = len(list(keep.glob("snippet_*.py"))) + 1
            (keep / f"snippet_{n:03d}.py").write_text(code or "")
        except Exception:  # noqa: BLE001
            pass
        # Force a headless matplotlib backend IF it's installed — never crash the
        # snippet just because matplotlib is absent. Then the RLM llm() primitive.
        header = ("try:\n    import matplotlib; matplotlib.use('Agg')\n"
                  "except Exception:\n    pass\n") + _LLM_HELPER
        script.write_text(header + (code or ""))
        env = _pydeps_env()   # agent-installed packages (persistent volume) importable
        try:
            from llm import current_model
            env["GARUDA_LLM_MODEL"] = current_model()   # snippet's llm() uses the active model
        except Exception:  # noqa: BLE001
            pass
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=str(base), env=env,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"(timed out after {timeout}s — do less work per call or split it up)"
        except Exception as e:  # noqa: BLE001
            return f"(could not run python: {e})"
        out = proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        tag = "OK" if proc.returncode == 0 else f"EXIT {proc.returncode}"
        return f"[{tag}]\n{out.strip()[-6000:] or '(no output)'}"

    @tool
    def pip_install(packages: str) -> str:
        """Install Python packages so `run_python` can import them. Pass names
        space- or comma-separated, e.g. 'numpy', 'torch', 'matplotlib scipy', 'pypdf
        pillow'. Call this BEFORE run_python when an import is missing. Installs
        land in a PERSISTENT environment (shared volume), so a package installed
        once stays available across runs and service restarts."""
        pkgs = [p for p in re.split(r"[,\s]+", (packages or "").strip()) if p]
        if not pkgs:
            return "(no packages given)"
        pydeps.mkdir(parents=True, exist_ok=True)
        attempts = [
            # persistent target dir on the workspace volume (survives rebuilds)
            [sys.executable, "-m", "pip", "install", "--target", str(pydeps),
             "--upgrade", *pkgs],
            [sys.executable, "-m", "pip", "install", *pkgs],
        ]
        if shutil.which("uv"):
            attempts.insert(1, ["uv", "pip", "install", "--python", sys.executable, *pkgs])
        last = ""
        for cmd in attempts:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600)
                if proc.returncode == 0:
                    # record for reproducibility / container rebuilds
                    try:
                        req = pydeps / "agent_requirements.txt"
                        have = set(req.read_text().split()) if req.is_file() else set()
                        req.write_text("\n".join(sorted(have | set(pkgs))) + "\n")
                    except Exception:  # noqa: BLE001
                        pass
                    return f"installed: {', '.join(pkgs)} (persistent)"
                last = (proc.stdout + proc.stderr)[-1500:]
            except Exception as e:  # noqa: BLE001
                last = str(e)
        return f"(pip install failed for {', '.join(pkgs)}: {last})"

    return [run_python, pip_install]


def build_deep_agent(base_dir: str | Path, model=None, temperature: float = 0.2):
    """A deepagents agent with planning + REAL file tools + the RLM `llm_query`
    delegation primitive, driven by the configured local model."""
    from deepagents import create_deep_agent
    return create_deep_agent(
        tools=make_fs_tools(base_dir) + make_rlm_tools(temperature),
        instructions=INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        # keep the planning tool; use OUR real-disk file tools instead of the
        # built-in virtual-filesystem ones (write_file/read_file/ls/edit_file).
        builtin_tools=["write_todos"],
    )


def build_step_agent(base_dir: str | Path, extra_tools=None, instructions: str | None = None,
                     temperature: float = 0.2, model=None, on_clean_write=None,
                     subagents=None):
    """A deep agent for ONE pipeline stage ("every agent is a deep agent"). Every node
    gets: planning (`write_todos`), real file tools (slice-read + grep), the RLM
    `llm_query` delegation primitive, the built-in `task` sub-agent tool, PLUS whatever
    step-specific tools (web research, memory, …) the caller passes. All driven by the
    configured local model. The fixed stage DAG still orchestrates the steps; this
    upgrades a single node's brain into an RLM. `on_clean_write` is threaded into
    write_file_disk (per-IP verify hook — see make_fs_tools). `subagents` (deepagents
    SubAgent dicts) adds NAMED specialist sub-agents callable via the `task` tool."""
    from deepagents import create_deep_agent
    tools = (list(make_fs_tools(base_dir, on_clean_write=on_clean_write))
             + list(make_rlm_tools(temperature))
             + list(make_python_tools(base_dir))
             + list(extra_tools or []))
    return create_deep_agent(
        tools=tools,
        instructions=instructions or INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        subagents=list(subagents or []),
        builtin_tools=["write_todos"],
    )


def _looks_repetitive(text: str) -> bool:
    """Detect a degenerate generation loop — the model spewing the same handful of
    lines over and over. If the last 30 non-empty lines collapse to ≤3 distinct
    lines, it's looping. Real code/reasoning almost never does that."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 30:
        return False
    return len(set(lines[-30:])) <= 3


def run_step_agent(base_dir: str | Path, goal: str, extra_tools=None,
                   instructions: str | None = None, temperature: float = 0.2,
                   model=None, on_clean_write=None, recursion_limit: int = 60,
                   log_name: str = "deep_agent") -> str:
    """Build + run a per-stage deep agent (planning + file + web + memory tools),
    logging every tool/task call to `logs/<log_name>.md` in the workspace. Returns
    the agent's final assistant text — service-side analog of GarudaChip's
    run_deep_agent/_stream_deep_agent, with the same loop guards.

    Loop guards: if the model repeats the SAME tool call, rewrites the SAME path
    over and over, or repeats the same reasoning with no tool call in between,
    the agent is stopped so it can't spin forever — the caller then proceeds
    with whatever is on disk (its own completeness check decides)."""
    base = Path(base_dir).resolve()
    agent = build_step_agent(base, extra_tools=extra_tools, instructions=instructions,
                             temperature=temperature, model=model,
                             on_clean_write=on_clean_write)
    log_path = base / "logs" / f"{log_name}.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_lines: List[str] = [f"# Deep agent transcript — {log_name}", "", f"GOAL:\n{goal}", ""]

    def _flush():
        try:
            log_path.write_text("\n".join(log_lines)[-400_000:])
        except Exception:  # noqa: BLE001
            pass

    seen, final = 0, ""
    calls: Dict[str, int] = {}
    writes: Dict[str, int] = {}      # per-PATH write count — catches fixation on ONE file
    ai_texts: Dict[str, int] = {}    # per-MESSAGE reasoning — catches "let me try again" spam
    stop = reason = ""
    # tools that ARE the work — never count these as "spinning". A write of a NEW path
    # clears the spin counter (real progress); but REWRITING the SAME path over and over
    # is fixation, not progress — so writes/path are bounded.
    _progress = {"write_file_disk", "run_python", "pip_install"}
    t0 = time.time()
    budget_s = float(os.getenv("GARUDA_DEEP_BUDGET_S", "2400"))
    max_writes_per_path = int(os.getenv("GARUDA_DEEP_MAX_WRITES_PER_PATH", "8"))
    max_same_call = int(os.getenv("GARUDA_DEEP_MAX_SAME_CALL", "4"))
    try:
        for state in agent.stream({"messages": [{"role": "user", "content": goal}]},
                                  stream_mode="values",
                                  config={"recursion_limit": recursion_limit}):
            if time.time() - t0 > budget_s:
                log_lines.append(f"\n⏳ deep-agent session hit its {int(budget_s)}s budget — "
                                 "proceeding with what it has.")
                break
            msgs = state.get("messages", [])
            for m in msgs[seen:]:
                mtype = getattr(m, "type", "")
                text = (getattr(m, "content", "") or "")
                if isinstance(text, list):
                    text = "\n".join(str(part.get("text", "")) if isinstance(part, dict)
                                     else str(part) for part in text)
                if mtype == "ai" and text.strip():
                    final = text.strip()
                    log_lines.append(f"\n**assistant:** {final[:2000]}")
                    # REASONING-LOOP guard: same reasoning repeats with NO tool call.
                    if len(text) > 40 and not (getattr(m, "tool_calls", None) or []):
                        key = re.sub(r"\s+", " ", text.lower())[:140]
                        ai_texts[key] = ai_texts.get(key, 0) + 1
                        if ai_texts[key] >= 3 or _looks_repetitive(text):
                            stop, reason = "loop", "repeating the same reasoning"
                elif mtype == "tool":
                    log_lines.append(f"\n> tool result: {str(text)[:800]}")
                for tc in (getattr(m, "tool_calls", None) or []):
                    if not isinstance(tc, dict):
                        continue
                    name = tc.get("name") or ""
                    args = tc.get("args") or {}
                    log_lines.append(f"\n**tool call:** `{name}` {str(args)[:400]}")
                    if name == "write_file_disk":
                        path = str(args.get("path", ""))
                        writes[path] = writes.get(path, 0) + 1
                        calls.clear()            # a write is progress → clear spin counter
                        if writes[path] >= max_writes_per_path:
                            stop, reason = "loop", f"rewrote {path} {writes[path]}×"
                    elif name in _progress:
                        calls.clear()
                    else:
                        key = f"{name}:{str(args)[:120]}"
                        calls[key] = calls.get(key, 0) + 1
                        if calls[key] >= max_same_call:
                            stop, reason = "loop", f"repeated {name} {calls[key]}×"
            seen = len(msgs)
            _flush()
            if stop:
                log_lines.append(f"\n🛑 stopped: {reason}")
                break
    except Exception as e:  # noqa: BLE001 — return what we have; caller decides
        log_lines.append(f"\n(deep agent aborted: {e})")
    _flush()
    return final
