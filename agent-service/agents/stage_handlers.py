"""Stage-specialized agent handlers.

Each handler receives a :class:`StageContext` (task info + resolved workspace +
prior memory + artifact inventory) and returns an :class:`AgentResult`.
Handlers write real files into the task workspace and also return them in
``workspace_files`` so the orchestrator can index them.

Two execution paths per LLM stage (GarudaChip parity):

* **Deep agents (default with a real provider)** — every LLM stage node runs a
  Recursive-Language-Model deep agent (:mod:`agents.deep_agent`): planning
  (`write_todos`), real on-disk file tools with compile-check-on-write, the
  `llm_query` delegation primitive, a Python sandbox, autonomous web research
  (`search_web`/`fetch_reference`) and persistent fix-lesson memory
  (`recall_memory`). Attached images/PDFs are read through the vision digest
  (``context/uploads_digest.md``).
* **Deterministic fallback (``LLM_PROVIDER=mock`` or deepagents unavailable)**
  — the original templated generation, so the stack keeps running end-to-end
  without any API key and the unit tests stay deterministic.

Every artifact carries its workspace-relative ``path`` so the UI can open it
(an artifact without a path renders as "Unavailable").
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from context import files as wsfiles
from reporting import collect_evidence, generate_pdf, generate_reports

from . import rtl_author
from .result import AgentResult


@dataclass
class StageContext:
    task_id: str
    stage: str
    prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    workspace: Optional[Path] = None
    memories: List[Any] = field(default_factory=list)
    artifact_inventory: List[str] = field(default_factory=list)
    eda_reports: List[str] = field(default_factory=list)
    reference_files: List[str] = field(default_factory=list)

    @property
    def task_name(self) -> str:
        return str(self.context.get("task_name", self.task_id))

    @property
    def design_brief(self) -> str:
        return str(self.context.get("design_brief") or self.context.get("spec") or self.prompt)

    @property
    def llm_model(self) -> Optional[str]:
        model = str(self.context.get("llm_model") or "").strip()
        return model or None

    @property
    def top_module(self) -> str:
        top = self.context.get("top_module") or self.context.get("top")
        if top:
            return str(top)
        return _slug(self.task_name) or "generated_top"

    def persist(self, files: Dict[str, str]) -> None:
        if self.workspace is not None:
            wsfiles.persist_workspace_files(self.workspace, files)

    def memory_hint(self) -> str:
        if self.memories:
            first = self.memories[0]
            return getattr(first, "decision", None) or "No prior diagnosis stored."
        return "No prior diagnosis stored."

    def uploads_digest(self) -> str:
        """The vision/PDF digest of the task's attached files ('' when none).
        The design brief rides along so each image is CLASSIFIED in context
        (architecture spec vs. chip-input data vs. reference)."""
        if self.workspace is None:
            return ""
        try:
            from uploads import ingest_uploads
            return ingest_uploads(self.workspace, brief=self.design_brief)
        except Exception:  # noqa: BLE001
            return ""


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return cleaned or "design"


def _diag(stage: str, agent: str, title: str, detail: str, confidence: str = "") -> Dict[str, Any]:
    return {
        "id": f"diag-{stage.lower()}",
        "title": title,
        "detail": detail,
        "confidence": confidence or "High · deterministic stage handler",
        "suggestedBy": agent,
    }


def _artifact(aid: str, name: str, atype: str, owner: str, path: str = "") -> Dict[str, Any]:
    """Artifact record for the UI. ``path`` (workspace-relative) is what makes
    the artifact openable — without it the frontend shows 'Unavailable'."""
    art = {"id": aid, "name": name, "type": atype, "owner": owner}
    if path:
        art["path"] = path
    return art


# --------------------------------------------------------------------------- #
# Deep-agent plumbing (GarudaChip parity)
# --------------------------------------------------------------------------- #
def _deep_enabled(sc: StageContext) -> bool:
    """Deep agents run when a real LLM provider is configured, deepagents is
    installed, and a workspace exists. AGENT_DEEP_AGENTS=0 disables them."""
    if os.getenv("AGENT_DEEP_AGENTS", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    if sc.workspace is None:
        return False
    try:
        from llm import get_provider
        if get_provider() == "mock":
            return False
        import deepagents  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _apply_model(sc: StageContext) -> None:
    """Apply the task's per-run model pick to the process-wide factory."""
    try:
        from llm import set_model
        set_model(sc.llm_model)
    except Exception:  # noqa: BLE001
        pass


def _run_deep(sc: StageContext, goal: str, log_name: str, on_clean_write=None,
              recursion_limit: int = 60) -> str:
    """Run one stage's deep agent (file + web + memory + python tools).

    A DeepAgentProviderError is re-raised with the provider and model named: the
    stage cannot do its work without an LLM, and a run that dies on an empty
    credit balance should say so rather than report an empty result as success."""
    from research import make_step_tools
    from .deep_agent import DeepAgentProviderError, run_step_agent
    _apply_model(sc)
    try:
        return run_step_agent(
            sc.workspace, goal,
            extra_tools=make_step_tools(sc.workspace),
            on_clean_write=on_clean_write,
            recursion_limit=recursion_limit,
            log_name=log_name,
        )
    except DeepAgentProviderError as e:
        from llm import current_model, get_provider
        raise RuntimeError(
            f"LLM provider refused the {sc.stage} run "
            f"(provider={get_provider()}, model={current_model()}): {e} "
            f"Transcript: logs/{log_name}.md"
        ) from e


_TEXT_EXT = {".v", ".sv", ".vh", ".svh", ".md", ".json", ".txt", ".mem", ".log", ".xdc",
             ".sdc", ".py", ".csv"}


def _files_from_disk(workspace: Path, subdirs: List[str], cap_bytes: int = 200_000) -> Dict[str, str]:
    """Snapshot text files under the given workspace subdirs (rtl/, tb/, …) so a
    deep agent's on-disk writes flow back through the stage result and get
    indexed by the orchestrator."""
    out: Dict[str, str] = {}
    for sub in subdirs:
        d = workspace / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in _TEXT_EXT:
                continue
            try:
                if p.stat().st_size > cap_bytes:
                    continue
                out[str(p.relative_to(workspace))] = p.read_text(errors="replace")
            except Exception:  # noqa: BLE001
                continue
    return out


def _digest_note(sc: StageContext, limit: int = 2500) -> str:
    digest = sc.uploads_digest()
    if not digest:
        return ""
    return ("\nATTACHED FILES (the user uploaded these with the task — build to them; the full "
            "digest is on disk at context/uploads_digest.md):\n" + digest[:limit] + "\n")


def _anchor_note(sc: StageContext) -> str:
    if sc.workspace is None or not (sc.workspace / "context" / "anchor").is_dir():
        return ""
    return ("\nREFERENCES: real HDL from the closest open-source design(s) is in "
            "`context/anchor/` and links are in `context/sources.md`. grep_files/"
            "read_file_disk the closest module to UNDERSTAND the correct approach "
            "(algorithm, interfaces, pitfalls), then WRITE YOUR OWN implementation "
            "adapted to the spec — study it, don't paste it.\n")


def _log_state(sc: StageContext, event: str, detail: str = "") -> None:
    """Append to the RUN JOURNAL (context/state.md) every deep agent reads FIRST
    (GarudaChip's `_log_state`): what has been built, what passed/failed, what
    the user asked — so no stage redoes or contradicts recorded work."""
    if sc.workspace is None:
        return
    try:
        from datetime import datetime
        p = sc.workspace / "context" / "state.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file():
            p.write_text("# Run journal\n\nEvery stage appends here; deep agents read this FIRST.\n\n")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with p.open("a") as f:
            f.write(f"- **{stamp} · {event}** — {detail}\n")
    except Exception:  # noqa: BLE001
        pass


def _planned_rtl_files(sc: StageContext) -> List[str]:
    """The rtl/ files the build contract commits to — from the GOLDEN_GEN
    contract (`context/golden_contract.md`) first, then the PLAN contract
    (`context/design_notes.md`). The generation completeness gate holds RTL_GEN
    to this list, which is what forces a MULTI-FILE decomposition instead of one
    big monolith."""
    if sc.workspace is None:
        return []
    files: List[str] = []
    for rel in ("context/golden_contract.md", "context/design_notes.md"):
        src = sc.workspace / rel
        if not src.is_file():
            continue
        for m in re.finditer(r"\brtl/([\w\-]+\.(?:sv|v|vh|svh|mem))\b",
                             src.read_text(errors="replace")):
            name = m.group(1)
            if name not in files:
                files.append(name)
    return files[:24]


# --------------------------------------------------------------------------- #
# Golden-model plumbing — the Python reference the RTL and TB stages must match
# --------------------------------------------------------------------------- #
_GOLDEN_SUMMARY_REL = "golden/golden_summary.json"
_GOLDEN_CONTRACT_REL = "context/golden_contract.md"
# Per-module engineering explanation + governing equations. The golden model is
# where the mathematics actually lives, so the agent that writes it is the one
# asked to state it; the IEEE report renders this verbatim.
_GOLDEN_MATH_REL = "golden/module_math.json"
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _golden_summary(sc: StageContext) -> Dict[str, Any]:
    """The machine-readable golden-model manifest (IP list, test results,
    preview outputs). ``{}`` when GOLDEN_GEN has not produced one yet."""
    if sc.workspace is None:
        return {}
    p = sc.workspace / _GOLDEN_SUMMARY_REL
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(errors="replace"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _golden_ips(sc: StageContext) -> List[Dict[str, Any]]:
    """The IP blocks the golden model defines: [{name, file, role, tier, ports}]."""
    ips = _golden_summary(sc).get("ips")
    return [ip for ip in ips if isinstance(ip, dict) and ip.get("name")] if isinstance(ips, list) else []


def _golden_vector_modules(sc: StageContext) -> List[str]:
    """Module names that have golden test vectors on disk (golden/vectors/<m>.json)."""
    if sc.workspace is None:
        return []
    vdir = sc.workspace / "golden" / "vectors"
    if not vdir.is_dir():
        return []
    return sorted(p.stem for p in vdir.glob("*.json"))


def _golden_note(sc: StageContext) -> str:
    """The standing instruction every post-GOLDEN stage carries: the Python
    model in `golden/` is the definition of correct, and the per-IP vectors are
    the expected values."""
    if sc.workspace is None or not (sc.workspace / _GOLDEN_CONTRACT_REL).is_file():
        return ""
    ips = _golden_ips(sc)
    vec = _golden_vector_modules(sc)
    lines = ["\nGOLDEN MODEL (the definition of CORRECT — already reviewed and APPROVED by the "
             "user): the Python reference implementation is in `golden/`, its build contract is "
             "`context/golden_contract.md`, and the human-readable spec is "
             "`golden/golden_report.md`. read_file_disk them BEFORE you write anything."]
    if ips:
        lines.append("The contract's IP blocks (implement EVERY one, same name, same interface, "
                     "same fixed-point format):")
        for ip in ips[:24]:
            lines.append(f"  - {ip.get('name')} [{ip.get('tier', 'ip')}] — {ip.get('role', '')}"
                         + (f" · ports: {ip.get('ports')}" if ip.get("ports") else ""))
    if vec:
        lines.append("Per-module GOLDEN TEST VECTORS (input → expected output, computed by the "
                     "Python model) live in: "
                     + ", ".join(f"golden/vectors/{m}.json" for m in vec[:24]))
    lines.append("Never re-derive, re-train or 'improve' the golden values — the RTL must "
                 "reproduce them BIT-EXACTLY. If the golden model looks wrong, say so instead "
                 "of silently diverging from it.\n")
    return "\n".join(lines)


def _rtl_hierarchy(workspace: Path) -> Dict[str, Any]:
    """Split the RTL on disk into the three tiers the flow requires:
    leaf **IPs**, **sub-toplevel** integrators, and the single **top**."""
    out: Dict[str, Any] = {"top": "", "subtops": [], "ips": [], "modules": {}, "multi_module": []}
    try:
        from verilog_check import parse_rtl, pick_top
    except Exception:  # noqa: BLE001
        return out
    try:
        info = parse_rtl(workspace / "rtl")
    except Exception:  # noqa: BLE001
        return out
    defs, insts = info.get("defs", {}), info.get("insts", {})
    out["modules"] = {name: meta.get("file", "") for name, meta in defs.items()}
    per_file: Dict[str, List[str]] = {}
    for name, meta in defs.items():
        per_file.setdefault(meta.get("file", ""), []).append(name)
    out["multi_module"] = sorted(f for f, mods in per_file.items() if len(mods) > 1 and f)
    try:
        out["top"] = pick_top(workspace / "rtl") or ""
    except Exception:  # noqa: BLE001
        out["top"] = ""
    for name in sorted(defs):
        if name == out["top"]:
            continue
        children = [c for c, _, _ in insts.get(name, []) if c in defs]
        (out["subtops"] if children else out["ips"]).append(name)
    return out


# --------------------------------------------------------------------------- #
# SPEC_INGEST — structured spec + attachment (image/PDF) digest
# --------------------------------------------------------------------------- #
def run_spec_ingest(sc: StageContext) -> AgentResult:
    agent = "SpecInterpreter"
    brief = sc.design_brief
    digest = sc.uploads_digest()
    attachments: List[str] = []
    if sc.workspace is not None:
        updir = sc.workspace / "context" / "uploads"
        if updir.is_dir():
            attachments = [p.name for p in sorted(updir.iterdir())
                           if p.is_file() and not p.name.startswith(".")]
    spec = {
        "task_id": sc.task_id,
        "top_module": sc.top_module,
        "interfaces": ["clk", "rst_n", "data_i", "data_o"],
        "constraints": {
            "clock_port": sc.context.get("clock_port", "clk"),
            "pdk_id": sc.context.get("pdk_id", ""),
        },
        "assumptions": ["Single clock domain", "Synchronous active-low reset"],
        "risks": ["Unspecified timing budget", "Testbench coverage may be partial"],
        "attachments": attachments,
    }
    brief_md = (
        f"# Design Brief — {sc.task_name}\n\n{brief}\n\n"
        f"## Interfaces\n" + "\n".join(f"- `{p}`" for p in spec["interfaces"]) + "\n\n"
        f"## Assumptions\n" + "\n".join(f"- {a}" for a in spec["assumptions"]) + "\n\n"
        f"## Risks\n" + "\n".join(f"- {r}" for r in spec["risks"]) + "\n"
        + (f"\n## Attached files\n" + "\n".join(f"- `{n}`" for n in attachments)
           + "\n\nThe attachment digest (vision model reading of images, extracted PDF text) "
             "is at `context/uploads_digest.md`.\n" if attachments else "")
    )
    files = {
        "spec/design_brief.md": brief_md,
        "spec/spec.json": json.dumps(spec, indent=2),
    }
    sc.persist(files)
    detail = "Extracted interfaces, constraints, assumptions and risks."
    if attachments:
        detail += f" Ingested {len(attachments)} attachment(s)" + (
            " and built the vision digest." if digest else ".")
    _log_state(sc, "spec_ingest:done",
               f"brief captured; attachments={attachments or 'none'}"
               + ("; vision digest at context/uploads_digest.md" if digest else ""))
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} decomposed the design brief for {sc.task_name} into a structured spec"
                + (f" (+{len(attachments)} attachment(s) digested)" if attachments else "") + ".",
        diagnostics=[_diag(sc.stage, agent, "Spec decomposition", detail)],
        artifacts=[_artifact("artifact-spec", "spec.json", "SPEC", agent, "spec/spec.json"),
                   _artifact("artifact-brief", "design_brief.md", "SPEC", agent, "spec/design_brief.md")],
        workspace_files=files,
        recommended_next="Review the structured plan and advance to PLAN.",
        structured_conclusion=spec,
        artifact_refs=list(files.keys()),
    )


# --------------------------------------------------------------------------- #
# PLAN — grand plan (deep agent + web research), deterministic fallback
# --------------------------------------------------------------------------- #
def run_plan(sc: StageContext) -> AgentResult:
    agent = "FlowAssistant"
    checklist = [
        "Generate RTL for top module and submodules",
        "Author a self-checking testbench",
        "Run simulation and confirm waveform",
        "Lint the RTL",
        "Harden to GDSII (SYNTH/PNR/DRC_LVS)",
        "Assemble signoff + final report",
    ]
    research_summary = ""
    deep_note = ""
    if _deep_enabled(sc):
        # 1) Reference hunt FIRST (understand → sources.md → anchor clone), so the
        #    plan is grounded in how the design is actually built.
        try:
            from research import gather_references, web_research_enabled
            if web_research_enabled():
                _apply_model(sc)
                info = gather_references(sc.design_brief, sc.workspace)
                research_summary = str(info.get("understanding") or "")
                if info.get("anchor_files"):
                    research_summary += f"\n(anchored {info['anchor_files']} reference HDL file(s))"
        except Exception:  # noqa: BLE001
            research_summary = ""
        # 2) The grand-planner deep agent writes the execution plan + build contract.
        goal = (
            f"You are the GRAND PLANNER for this chip design task: {sc.design_brief}\n"
            + _digest_note(sc)
            + _anchor_note(sc)
            + (f"\nWEB UNDERSTANDING (from research):\n{research_summary}\n" if research_summary else "")
            + "\nWrite TWO files with write_file_disk:\n"
              "1. `plans/execution_plan.md` — the ordered plan: research/references used, the "
              "module map (EVERY rtl/<file>.v you intend, one line each: file — module — role — "
              "key ports/widths), then testbench, simulation, lint, harden, report steps.\n"
              "2. `context/design_notes.md` — the BUILD CONTRACT the generator follows: the same "
              "module map as a table (| module | file | role | ports |), interfaces between "
              "modules (signal names, widths, direction), and the top module name.\n"
              "Ground the module map in the anchor references when present. Plan ONLY — do NOT "
              "write RTL. When both files are written, reply 'done'."
        )
        deep_note = _run_deep(sc, goal, "plan_deep_agent", recursion_limit=40)

    files: Dict[str, str] = {}
    plan_path = sc.workspace / "plans" / "execution_plan.md" if sc.workspace else None
    if not (plan_path and plan_path.is_file()):
        plan_md = (
            f"# Execution Plan — {sc.task_name}\n\n"
            f"Top module: `{sc.top_module}`\n\n## Checklist\n"
            + "\n".join(f"- [ ] {c}" for c in checklist)
            + "\n"
        )
        files["plans/execution_plan.md"] = plan_md
        sc.persist(files)
    if sc.workspace is not None:
        files.update(_files_from_disk(sc.workspace, ["plans"]))
        # Named context artifacts only — never the whole anchor/reference tree.
        for rel in ("context/design_notes.md", "context/sources.md", "context/understanding.md"):
            p = sc.workspace / rel
            if p.is_file():
                files[rel] = p.read_text(errors="replace")

    artifacts = [_artifact("artifact-plan", "execution_plan.md", "PLAN", agent, "plans/execution_plan.md")]
    if "context/design_notes.md" in files:
        artifacts.append(_artifact("artifact-design-notes", "design_notes.md", "PLAN", agent,
                                   "context/design_notes.md"))
    if "context/sources.md" in files:
        artifacts.append(_artifact("artifact-sources", "sources.md", "REFERENCE", agent,
                                   "context/sources.md"))
    mode = "deep agent + web research" if deep_note else "deterministic checklist"
    _log_state(sc, "plan:done",
               f"mode={mode}; planned rtl files={_planned_rtl_files(sc) or 'unspecified'}")
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} produced an execution plan for {sc.task_name} ({mode}).",
        diagnostics=[_diag(sc.stage, agent, "Execution plan",
                           (research_summary[:300] + " — " if research_summary else "")
                           + "Generated a staged implementation plan and build contract.",
                           confidence="Deep agent" if deep_note else "")],
        artifacts=artifacts,
        workspace_files=files,
        recommended_next="Advance to GOLDEN_GEN and build the Python golden model.",
        structured_conclusion={"checklist": checklist, "deep_agent": bool(deep_note),
                               "web_research": bool(research_summary)},
        artifact_refs=list(files.keys()),
    )


# --------------------------------------------------------------------------- #
# GOLDEN_GEN — executable Python reference model + per-IP tests (human-gated)
# --------------------------------------------------------------------------- #
def _chip_data_images(sc: StageContext) -> List[str]:
    """Attached images the vision triage classified as CHIP INPUT DATA (the
    picture the accelerator processes) — not architecture diagrams."""
    if sc.workspace is None:
        return []
    try:
        from uploads import uploads_manifest
        manifest = uploads_manifest(sc.workspace)
    except Exception:  # noqa: BLE001
        return []
    return [name for name, role in (manifest or {}).items() if role == "data"]


def _run_golden_tests(sc: StageContext) -> Dict[str, Any]:
    """Run the golden model's own pytest suite OURSELVES (never trust the
    agent's self-report) and write `golden/test_results.json` + the raw log.

    Falls back to executing each `golden/tests/test_*.py` as a plain script when
    pytest is unavailable, so a design whose tests are written as `__main__`
    scripts is still verified."""
    result: Dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "ran": False,
                              "files": [], "log": ""}
    if sc.workspace is None:
        return result
    tests_dir = sc.workspace / "golden" / "tests"
    test_files = sorted(p for p in tests_dir.glob("test_*.py")) if tests_dir.is_dir() else []
    result["files"] = [str(p.relative_to(sc.workspace)) for p in test_files]
    if not test_files:
        return result

    import subprocess
    import sys as _sys
    env = dict(os.environ)
    # The model package (golden/model/...) and any agent-pip-installed library
    # must import from inside the tests.
    pydeps = os.getenv("AGENT_PYDEPS_DIR") or str(
        Path(os.getenv("AGENT_ARTIFACT_ROOT",
                       os.getenv("WORKSPACE_ROOT", "/tmp/chip-orchestra/workspaces"))) / ".pydeps")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(sc.workspace), str(sc.workspace / "golden"), pydeps, env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["MPLBACKEND"] = "Agg"
    timeout = int(os.getenv("GOLDEN_TEST_TIMEOUT_S", "900"))

    def _run(cmd: List[str]) -> "subprocess.CompletedProcess":
        return subprocess.run(cmd, cwd=str(sc.workspace), env=env, capture_output=True,
                              text=True, errors="replace", timeout=timeout)

    log = ""
    try:
        proc = _run([_sys.executable, "-m", "pytest", "golden/tests", "-q", "--no-header",
                     "-p", "no:cacheprovider"])
        log = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        if proc.returncode == 4 or "No module named pytest" in log:
            raise FileNotFoundError("pytest unavailable")
        result["ran"] = True
        passed = sum(int(m) for m in re.findall(r"(\d+)\s+passed", log))
        failed = sum(int(m) for m in re.findall(r"(\d+)\s+(?:failed|error)", log))
        result.update(passed=passed, failed=failed, total=passed + failed)
        # A clean exit with no recognizable counters still means the suite ran green.
        if proc.returncode == 0 and not result["total"]:
            result.update(passed=len(test_files), total=len(test_files))
        # rc 5 = "no tests collected". Reporting that as a failure would send the
        # agent hunting a broken test; the truth is that nothing asserted, which
        # the gap check words correctly on its own.
        elif proc.returncode not in (0, 5) and not failed:
            result["failed"] = 1
            result["total"] = result["passed"] + 1
    except Exception as exc:  # noqa: BLE001 — pytest missing/exploded → run the scripts
        log = f"(pytest unavailable or crashed: {exc}) — running each test file directly\n"
        passed = failed = 0
        for p in test_files:
            try:
                proc = _run([_sys.executable, str(p.relative_to(sc.workspace))])
                ok = proc.returncode == 0
                passed, failed = passed + int(ok), failed + int(not ok)
                log += (f"\n$ python {p.relative_to(sc.workspace)} → "
                        f"{'PASS' if ok else 'FAIL'}\n"
                        + ((proc.stdout or "") + (proc.stderr or ""))[-2000:])
            except Exception as inner:  # noqa: BLE001
                failed += 1
                log += f"\n$ python {p.name} → ERROR {inner}\n"
        result.update(ran=True, passed=passed, failed=failed, total=passed + failed)

    result["log"] = log[-20000:]
    try:
        (sc.workspace / "golden").mkdir(parents=True, exist_ok=True)
        (sc.workspace / "golden" / "test_log.txt").write_text(result["log"])
        (sc.workspace / "golden" / "test_results.json").write_text(
            json.dumps({k: v for k, v in result.items() if k != "log"}, indent=2))
    except Exception:  # noqa: BLE001
        pass
    return result


def _render_golden_previews(sc: StageContext) -> List[str]:
    """Render the golden model's ``.mem`` dumps to PNGs so the approval gate can
    SHOW the computed result. SIM does this for the chip's own output, but that
    runs long after this gate — the reviewer needs the picture now. Deterministic
    on our side rather than asked of the agent; returns what was rendered."""
    if sc.workspace is None:
        return []
    rendered: List[str] = []
    try:
        from memimg import render_mem_image
    except Exception:  # noqa: BLE001
        return []
    waves = sc.workspace / "waves"
    for name in ("golden_output.mem", "chip_input.mem"):
        mem = waves / name
        png = mem.with_suffix(".png")
        if mem.is_file() and (not png.is_file() or png.stat().st_mtime < mem.stat().st_mtime):
            if render_mem_image(mem, png, workspace=sc.workspace):
                rendered.append(f"waves/{png.name}")
    # The canonical stimulus lives in rtl/*.mem; render the input alongside the
    # desired output so the reviewer sees the pair.
    if not (waves / "chip_input.png").is_file():
        rtl = sc.workspace / "rtl"
        if rtl.is_dir():
            for mem in sorted(rtl.glob("*input*.mem")):
                if render_mem_image(mem, waves / "chip_input.png", workspace=sc.workspace):
                    rendered.append("waves/chip_input.png")
                    break
    return rendered


def _golden_previews(sc: StageContext) -> List[Dict[str, str]]:
    """Everything worth SHOWING the user in the approval popup: the rendered
    golden output(s), the chip input, plots/waveforms and value dumps."""
    if sc.workspace is None:
        return []
    previews: List[Dict[str, str]] = []
    seen = set()

    def add(rel: str, label: str, kind: str) -> None:
        if rel in seen or not (sc.workspace / rel).is_file():
            return
        seen.add(rel)
        previews.append({"kind": kind, "path": rel, "label": label})

    # EXACTLY two panels: what goes in, and what must come out. The gate asks a
    # single question ("is this output correct?"), and the agent also writes
    # near-duplicate renders under golden/outputs/ (input_32x32, sobel_output,
    # sobel_comparison, …). Showing all of them buried the comparison that
    # actually decides the answer, so everything else stays out of the popup —
    # it is all still on disk and reachable from the RTL Workspace tab.
    add("waves/chip_input.png", "Chip input (as the model reads it)", "image")
    add("waves/golden_output.png", "Golden model output — the desired result", "image")

    # Fallbacks, only when a canonical render is missing: pick the single best
    # candidate per slot rather than listing every file in the directory.
    def first_match(pattern: str, label: str) -> None:
        directory = sc.workspace / "golden" / "outputs"
        if not directory.is_dir():
            return
        for p in sorted(directory.iterdir()):
            if (p.is_file() and p.suffix.lower() in _IMAGE_EXT
                    and re.search(pattern, p.name, re.I)):
                add(f"golden/outputs/{p.name}", label, "image")
                return

    if not (sc.workspace / "waves" / "chip_input.png").is_file():
        first_match(r"input", "Chip input (as the model reads it)")
    if not (sc.workspace / "waves" / "golden_output.png").is_file():
        first_match(r"output|result|golden", "Golden model output — the desired result")
    return previews[:2]


def _write_golden_summary(sc: StageContext, tests: Dict[str, Any]) -> Dict[str, Any]:
    """Merge whatever the agent declared in `golden/golden_summary.json` with
    what is ACTUALLY on disk, and write the merged manifest back. This is the
    payload the approval popup renders, so it must never lie about the run."""
    summary = _golden_summary(sc)
    hierarchy_ips = summary.get("ips") if isinstance(summary.get("ips"), list) else []
    ips = [ip for ip in hierarchy_ips if isinstance(ip, dict) and ip.get("name")]
    models = []
    vectors = _golden_vector_modules(sc)
    if sc.workspace is not None:
        mdir = sc.workspace / "golden" / "model"
        if mdir.is_dir():
            models = sorted(str(p.relative_to(sc.workspace)) for p in mdir.rglob("*.py"))
    # Fill an empty/absent IP list from the model files that exist, so the popup
    # still describes the design when the agent skipped the manifest.
    if not ips and models:
        ips = [{"name": Path(m).stem, "file": m, "tier": "ip", "role": ""} for m in models
               if Path(m).stem not in ("__init__", "top")]
    merged = {
        "top": summary.get("top") or sc.top_module,
        "design_brief": sc.design_brief[:600],
        "ips": ips,
        "models": models,
        "vectors": vectors,
        "tests": {k: v for k, v in tests.items() if k != "log"},
        "previews": _golden_previews(sc),
        "notes": summary.get("notes", ""),
        "report": "golden/golden_report.md"
        if (sc.workspace and (sc.workspace / "golden" / "golden_report.md").is_file()) else "",
        "contract": _GOLDEN_CONTRACT_REL
        if (sc.workspace and (sc.workspace / _GOLDEN_CONTRACT_REL).is_file()) else "",
    }
    if sc.workspace is not None:
        try:
            (sc.workspace / "golden").mkdir(parents=True, exist_ok=True)
            (sc.workspace / _GOLDEN_SUMMARY_REL).write_text(json.dumps(merged, indent=2))
        except Exception:  # noqa: BLE001
            pass
    return merged


def _golden_gaps(sc: StageContext, tests: Dict[str, Any], needs_output: bool) -> List[str]:
    """Deterministic completeness check — what the golden deliverable is still
    missing. Asking the agent nicely is not enough; these are the artifacts the
    RTL/TB stages and the human gate actually consume."""
    if sc.workspace is None:
        return []
    ws = sc.workspace
    gaps: List[str] = []
    models = sorted((ws / "golden" / "model").rglob("*.py")) if (ws / "golden" / "model").is_dir() else []
    if not models:
        gaps.append("golden/model/<ip>.py — no Python model exists yet. Write ONE module per IP "
                    "block plus the sub-toplevel and the toplevel model.")
    if not (ws / "golden" / "tests").is_dir() or not list((ws / "golden" / "tests").glob("test_*.py")):
        gaps.append("golden/tests/test_<ip>.py — no tests exist. Every IP, every sub-toplevel and "
                    "the toplevel needs its own test file with real expected values.")
    elif not tests.get("ran"):
        gaps.append("the test suite did not execute — fix the imports/syntax so "
                    "`python -m pytest golden/tests -q` runs from the workspace root.")
    elif tests.get("failed"):
        gaps.append(f"{tests['failed']} golden test(s) FAIL — see golden/test_log.txt and fix the "
                    "MODEL (or the test's expectation if that is what is wrong). The golden "
                    "model must be green before any RTL is written.")
    elif not tests.get("passed"):
        gaps.append("the test suite ran but asserted nothing — write tests that CHECK computed "
                    "values against independently known-correct results.")
    if not _golden_vector_modules(sc):
        gaps.append("golden/vectors/<module>.json — no test vectors were exported. Each file is "
                    '{"module":..., "ports":{"inputs":[[name,width]],"outputs":[[name,width]]}, '
                    '"vectors":[{"inputs":{...},"expected":{...}}]} with INTEGER (already '
                    "quantized) values — TB_GEN turns them into the Verilog testbenches.")
    if not (ws / "golden" / "golden_report.md").is_file():
        gaps.append("golden/golden_report.md — the human-readable spec (architecture, IP table, "
                    "fixed-point formats, what each test proves, what the output means).")
    if not (ws / _GOLDEN_CONTRACT_REL).is_file():
        gaps.append(f"{_GOLDEN_CONTRACT_REL} — the BUILD CONTRACT for RTL_GEN/TB_GEN: a table of "
                    "| module | rtl/<file>.v | tier (ip/subtop/top) | role | ports (name, dir, "
                    "width) | and the fixed-point format of every datapath signal.")
    if not (ws / _GOLDEN_SUMMARY_REL).is_file():
        gaps.append(f"{_GOLDEN_SUMMARY_REL} — the manifest the review popup renders: "
                    '{"top":..., "ips":[{"name","file","tier","role","ports"}], "notes":...}')
    if not (ws / _GOLDEN_MATH_REL).is_file():
        gaps.append(f"{_GOLDEN_MATH_REL} — the per-module explanation + governing equations "
                    'the IEEE report renders: {"algorithm":{"summary","equations":[latex]}, '
                    '"modules":[{"name","purpose","io","equations":[latex]}]}, covering every '
                    "module in the build contract.")
    if not _golden_previews(sc):
        gaps.append("a VISIBLE result — the user has to approve the golden output before RTL "
                    "starts. Render the toplevel model's output for the canonical input to "
                    "`golden/outputs/<name>.png` (matplotlib, Agg backend: image in → image out "
                    "for a vision accelerator, a signal/waveform plot for a datapath, a bar/"
                    "scatter of the computed values otherwise) and/or dump the key numbers to "
                    "`golden/outputs/<name>.json`.")
    if needs_output:
        golden_mem = ws / "waves" / "golden_output.mem"
        if not golden_mem.is_file():
            gaps.append("waves/golden_output.mem — the DESIRED chip output for the canonical "
                        "input, same N*N row-major hex format as the input mem. SIM compares the "
                        "RTL's chip_output.mem against it value by value.")
        # waves/golden_output.png is NOT asked of the agent: _render_golden_previews
        # renders it from the .mem deterministically, with the same palette the
        # SIM-stage renders use, so the reviewer compares like with like.
    return gaps


_GOLDEN_TEMPLATE_MODEL = '''"""Golden reference model — {top}.

Deterministic template written by the GOLDEN_GEN fallback (no LLM provider
configured). Replace the body with the real algorithm: the RTL and the
testbenches are generated to match THIS file's numbers bit-exactly.
"""


def {top}(data_in: int, width: int = 8) -> int:
    """One transaction of the toplevel. Integer in, integer out."""
    mask = (1 << width) - 1
    return (data_in + 1) & mask
'''

_GOLDEN_TEMPLATE_TEST = '''"""Golden tests — {top}. Every vector is an independently known-correct value."""
from model.{top} import {top}

VECTORS = [(0, 1), (1, 2), (254, 255), (255, 0)]


def test_{top}_vectors():
    for data_in, expected in VECTORS:
        assert {top}(data_in) == expected, f"{top}({{data_in}}) != {{expected}}"
'''


def run_golden_gen(sc: StageContext) -> AgentResult:
    """GOLDEN_GEN — build the executable Python reference model BEFORE any RTL.

    The stage writes a per-IP Python implementation, a sub-toplevel and a
    toplevel model, a real test suite for every one of them, exported per-module
    test vectors, and a rendered/numeric preview of the toplevel result. The
    tests are executed here (not self-reported), then the stage hands the
    preview to the human gate: the orchestrator holds GOLDEN_GEN in
    AWAITING_APPROVAL until the user confirms the output is correct, and only
    then does RTL_GEN start."""
    agent = "GoldenModeler"
    top = sc.top_module
    data_images = _chip_data_images(sc)
    has_mem_input = bool(sc.workspace and list((sc.workspace / "rtl").glob("*.mem"))) \
        if (sc.workspace and (sc.workspace / "rtl").is_dir()) else False
    needs_output = bool(data_images) or has_mem_input

    if _deep_enabled(sc):
        canonical = (sc.workspace / "context" / "chip_input_grid.json").is_file()
        input_note = ""
        if data_images:
            input_note = (
                "\nCHIP INPUT DATA: the attached image(s) "
                + ", ".join(f"`context/uploads/{n}`" for n in data_images)
                + " are what the chip PROCESSES (classified by the vision triage; "
                  "architecture diagrams are NOT chip input).\n"
                + ("A CANONICAL input already exists — `context/chip_input_grid.json` "
                   "(+ rtl/*_input.mem). REUSE IT EXACTLY; re-deriving it produces a "
                   "different input every run.\n"
                   "OVERRIDE — this is a REWORK and the reviewer's correction above is "
                   "about the INPUT ITSELF (its framing/crop/scale/region, e.g. \"the 32x32 "
                   "must show the road\", \"it is cropped\", \"wrong part of the image\"): "
                   "then the canonical input is what they are rejecting, so REUSE IS WRONG. "
                   "DELETE `context/chip_input_grid.json` and `rtl/*_input.mem` and "
                   "RE-DERIVE them per the FRAMING rule below, then re-run the model. "
                   "Reusing an input the reviewer just rejected makes the correction "
                   "impossible to satisfy and the gate will fail again identically.\n"
                   if canonical else
                   "DERIVE the input DETERMINISTICALLY with run_python: SAMPLE the image "
                   "programmatically (pip_install pillow numpy; read pixels, classify by "
                   "threshold) — use `context/uploads_digest.md` only for dimensions and "
                   "semantics, NEVER eyeball or invent values. "
                   "Save the parsed input to "
                   "`context/chip_input_grid.json`, write the stimulus the RTL will load to "
                   "`rtl/<name>.mem` ($readmemh format), and the side length to "
                   "`context/input_size.txt`.\n")
                # FRAMING is stated for BOTH branches: on a rework the canonical
                # branch is the one that re-derives, and it used to never see
                # this rule — so the crop survived every correction.
                + "FRAMING (mandatory, whenever you derive or re-derive the input): "
                  "DOWNSCALE THE WHOLE IMAGE to N*N with `PIL.Image.resize((N, N))` after a "
                  "grayscale convert. NEVER crop, slice, or take a sub-window — cropping "
                  "keeps a tiny patch (e.g. one lane marking or a flat region) and throws "
                  "away the scene the user actually uploaded, which makes the golden output "
                  "meaningless. The full subject must still be recognizable in the N*N grid. "
                  "Save the visualization to `waves/chip_input.png` as a SIDE-BY-SIDE panel — "
                  "original upload, grayscale, then the N*N grid the chip actually reads "
                  "(nearest-neighbour upscaled so it is visible) — so the reviewer can "
                  "confirm at a glance that the framing kept the whole scene.\n"
                + "Run the TOPLEVEL golden model on that canonical input, write the desired "
                  "result to `waves/golden_output.mem` (SAME N*N row-major hex format as the "
                  "input mem) — it is rendered to `waves/golden_output.png` for you. For a "
                  "pathfinding/navigation design the solved path cells MUST be marked with "
                  "value 4 so the render actually SHOWS the route "
                  "(0=white,1=black,2=red start,3=green goal,4=blue path).\n")
        elif has_mem_input:
            input_note = ("\nThe design loads .mem data: run the toplevel golden model on it and "
                          "write the desired result to `waves/golden_output.mem` (rendered to "
                          "`waves/golden_output.png` for you) — SIM compares the chip against "
                          "it.\n")

        goal = (
            "You are the GOLDEN MODELER. BEFORE a single line of Verilog exists, build the "
            f"EXECUTABLE PYTHON REFERENCE for this chip: {sc.design_brief}\n"
            "This model is the DEFINITION OF CORRECT: RTL_GEN implements it in hardware and "
            "TB_GEN turns its vectors into testbenches, so every number it produces is a "
            "hardware requirement. Work in Python with run_python (pip_install numpy / pillow / "
            "matplotlib / torch as needed).\n"
            + _digest_note(sc)
            + _anchor_note(sc)
            + input_note +
            "\nDELIVERABLES (write each with write_file_disk):\n"
            "1. `golden/model/<ip>.py` — ONE file per IP BLOCK of the architecture, mirroring "
            "the hardware decomposition you are about to build: the leaf IPs (datapath, memory/"
            "buffer, control FSM, arithmetic units, quantizer, …), then the SUB-TOPLEVEL "
            "module(s) that wire IPs into a subsystem, then `golden/model/top.py` — the "
            "TOPLEVEL that wires the sub-toplevels together and exposes the chip's function. "
            "Model the HARDWARE, not just the maths: integer/fixed-point only at the "
            "boundaries (state the Qm.n format), explicit bit widths, explicit reset/valid "
            "handshakes where the hardware will have them. Floating point is allowed INSIDE "
            "training/derivation only — everything the RTL must reproduce is quantized.\n"
            "   Example (RL accelerator): build the policy network in Python, TRAIN/derive the "
            "weights so it actually solves the canonical input, QUANTIZE them to the chosen "
            "fixed-point format, and write them to `rtl/<name>.mem` ($readmemh) — the weights "
            "are part of the chip. Then model each IP: mem/weight fetch, MAC array, activation "
            "LUT, accumulator, argmax/policy step, the environment step, and the controller.\n"
            "2. `golden/tests/test_<ip>.py` — a REAL test per IP, per sub-toplevel and for the "
            "toplevel. Directed vectors with INDEPENDENTLY known-correct expected values "
            "(hand-computed, closed-form, or a second implementation), edge cases (zero, max, "
            "overflow/saturation, reset), and for the toplevel an end-to-end check on the "
            "canonical input. `assert` every one — a test that only prints proves nothing. "
            "Import as `from model.<ip> import ...` (the runner puts `golden/` on PYTHONPATH); "
            "add `golden/model/__init__.py`.\n"
            "3. `golden/vectors/<module>.json` — the SAME vectors exported for hardware, one "
            "file per module you tested: {\"module\": name, \"ports\": {\"inputs\": [[name, "
            "width]], \"outputs\": [[name, width]]}, \"vectors\": [{\"inputs\": {...}, "
            "\"expected\": {...}}]}. Values are INTEGERS already in the RTL's encoding "
            "(quantized, two's complement for signed). TB_GEN bakes these into "
            "`tb/<module>_tb.v`, so a module without vectors cannot be verified.\n"
            "4. `golden/outputs/` — the VISIBLE result: run the toplevel model on the canonical "
            "input and render what it computed (matplotlib is forced to the Agg backend — "
            "savefig, never show). An image-processing accelerator saves the processed IMAGE, a "
            "datapath saves a signal/waveform plot, anything else saves a plot of the key "
            "values; also dump the headline numbers to `golden/outputs/<name>.json`. The user "
            "APPROVES this output before any RTL is generated.\n"
            "5. `golden/golden_report.md` — the spec a human reads: architecture + IP table, "
            "each IP's interface and fixed-point format, the algorithm, what each test proves, "
            "and how to read the output.\n"
            f"6. `{_GOLDEN_CONTRACT_REL}` — the BUILD CONTRACT the RTL and TB stages follow: a "
            "table `| module | rtl/<file>.v | tier (ip/subtop/top) | role | ports (name, dir, "
            "width) |` naming EVERY Verilog file to be written (plain Verilog-2001 `.v`, one "
            "module per file), the fixed-point formats, the .mem data files, and the top "
            "module name.\n"
            f"7. `{_GOLDEN_SUMMARY_REL}` — the manifest the review popup renders: {{\"top\": "
            "name, \"ips\": [{\"name\", \"file\", \"tier\", \"role\", \"ports\"}], \"notes\": "
            "\"what the user should look at\"}.\n"
            f"8. `{_GOLDEN_MATH_REL}` — the ENGINEERING EXPLANATION the final IEEE paper "
            "renders, as JSON: {\"algorithm\": {\"summary\": \"2-4 sentences on what the chip "
            "computes\", \"equations\": [\"...\"]}, \"modules\": [{\"name\": \"<rtl module>\", "
            "\"purpose\": \"2-3 sentences: what it computes and why it exists\", \"io\": "
            "\"key ports in -> out\", \"equations\": [\"...\"]}]}. Cover EVERY module in the "
            "build contract. Each entry in an \"equations\" list is a LaTeX math BODY ONLY — "
            "no dollar signs, no \\\\begin{equation} wrapper (the report adds it). Use real "
            "mathematics from the algorithm you implemented, e.g. for a Sobel operator the "
            "kernels and the gradient magnitude: \"G_x = I * \\\\begin{bmatrix} -1 & 0 & 1 \\\\\\\\ "
            "-2 & 0 & 2 \\\\\\\\ -1 & 0 & 1 \\\\end{bmatrix}\" and \"|G| = \\\\sqrt{G_x^2 + G_y^2}\", "
            "plus the fixed-point quantization actually used. NEVER invent mathematics the "
            "golden model does not implement — state what your Python code does.\n"
            "\nFINALLY run the suite yourself: run_python `import subprocess, sys; "
            "print(subprocess.run([sys.executable,'-m','pytest','golden/tests','-q'], "
            "capture_output=True, text=True).stdout[-3000:])` and fix whatever fails. Do NOT "
            "weaken a test to make it pass. Reply 'done' only when every test passes and every "
            "deliverable above exists."
        )
        _run_deep(sc, goal, "golden_gen_deep_agent", recursion_limit=90)

        tests = _run_golden_tests(sc)
        _render_golden_previews(sc)
        gaps = _golden_gaps(sc, tests, needs_output)
        for _pass in range(3):
            if not gaps:
                break
            _run_deep(
                sc,
                "Your GOLDEN MODEL is INCOMPLETE. The flow cannot continue until these are "
                f"fixed (design: {sc.design_brief}):\n- " + "\n- ".join(gaps)
                + "\nFix exactly these, keep everything that already works, re-run "
                  "`python -m pytest golden/tests -q` yourself, and reply 'done'.",
                f"golden_gen_deep_agent_fix{_pass + 1}", recursion_limit=60)
            tests = _run_golden_tests(sc)
            _render_golden_previews(sc)
            gaps = _golden_gaps(sc, tests, needs_output)

        # The gate asks a human "is this output correct?" — that question is
        # meaningless when the agent produced no model and no test ever ran.
        # Fail the stage instead of parking in AWAITING_APPROVAL, so the run
        # stops at the real cause rather than at an empty review popup.
        models_on_disk = sorted((sc.workspace / "golden" / "model").glob("*.py")) \
            if (sc.workspace / "golden" / "model").is_dir() else []
        models_on_disk = [p for p in models_on_disk if p.name != "__init__.py"]
        if not models_on_disk and not tests.get("ran"):
            raise RuntimeError(
                "GOLDEN_GEN produced no golden model: `golden/model/` is empty and the test "
                "suite never ran, so there is nothing for a human to approve. The deep-agent "
                f"transcripts in `logs/golden_gen_deep_agent*.md` hold the cause. Outstanding "
                f"gaps: {'; '.join(gaps) if gaps else 'none recorded'}."
            )

        summary = _write_golden_summary(sc, tests)
        top = summary.get("top") or top
        files = _files_from_disk(sc.workspace, ["golden"])
        for rel in (_GOLDEN_CONTRACT_REL, "context/chip_input_grid.json", "context/input_size.txt"):
            p = sc.workspace / rel
            if p.is_file():
                files[rel] = p.read_text(errors="replace")
        green = bool(tests.get("ran") and tests.get("passed") and not tests.get("failed"))
        ip_names = [ip.get("name", "") for ip in summary.get("ips", [])]
        _log_state(sc, "golden:done",
                   f"ips={ip_names or 'unspecified'}; tests={tests.get('passed', 0)} passed/"
                   f"{tests.get('failed', 0)} failed; previews="
                   f"{[p['path'] for p in summary.get('previews', [])] or 'none'}; "
                   f"gaps={gaps or 'none'}")

        artifacts = [_artifact("artifact-golden-summary", "golden_summary.json", "GOLDEN", agent,
                               _GOLDEN_SUMMARY_REL)]
        if "golden/golden_report.md" in files:
            artifacts.append(_artifact("artifact-golden-report", "golden_report.md", "REPORT",
                                       agent, "golden/golden_report.md"))
        if _GOLDEN_CONTRACT_REL in files:
            artifacts.append(_artifact("artifact-golden-contract", "golden_contract.md", "PLAN",
                                       agent, _GOLDEN_CONTRACT_REL))
        for preview in summary.get("previews", [])[:6]:
            artifacts.append(_artifact(f"artifact-golden-{_slug(preview['path'])}",
                                       Path(preview["path"]).name, "GOLDEN", agent,
                                       preview["path"]))
        return AgentResult(
            agent_name=agent,
            summary=f"{agent} built the Python golden model for {sc.task_name}: "
                    f"{len(ip_names) or len(summary.get('models', []))} IP model(s), "
                    f"{tests.get('passed', 0)}/{tests.get('total', 0)} test(s) passing"
                    + ("" if green else " — TESTS NOT GREEN")
                    + ". Awaiting your review of the golden output before RTL_GEN.",
            diagnostics=[_diag(sc.stage, agent, "Golden model + verification",
                               f"IPs: {', '.join(ip_names) or 'see golden/model/'}. "
                               f"Tests: {tests.get('passed', 0)} passed, "
                               f"{tests.get('failed', 0)} failed. "
                               f"Vectors: {', '.join(summary.get('vectors', [])) or 'none'}. "
                               + (f"Outstanding gaps: {'; '.join(g[:80] for g in gaps)}"
                                  if gaps else "All golden deliverables present."),
                               confidence="Deep agent")],
            artifacts=artifacts,
            workspace_files=files,
            recommended_next="Review the golden model output — approve it to start RTL_GEN, "
                             "or reject with a correction and the model is rebuilt.",
            structured_conclusion={
                "top_module": top,
                "ips": summary.get("ips", []),
                "models": summary.get("models", []),
                "vectors": summary.get("vectors", []),
                "tests": _tests_summary(tests),
                "previews": summary.get("previews", []),
                "gaps": gaps,
                "tests_green": green,
                "awaiting_review": True,
            },
            artifact_refs=list(files.keys()),
        )

    # Deterministic fallback (no LLM provider): a runnable skeleton so the DAG,
    # the approval gate and the tests stay exercisable end-to-end.
    model_top = _slug(top)
    files = {
        "golden/model/__init__.py": "",
        f"golden/model/{model_top}.py": _GOLDEN_TEMPLATE_MODEL.format(top=model_top),
        f"golden/tests/test_{model_top}.py": _GOLDEN_TEMPLATE_TEST.format(top=model_top),
        f"golden/vectors/{model_top}.json": json.dumps({
            "module": model_top,
            "ports": {"inputs": [["data_in", 8]], "outputs": [["data_out", 8]]},
            "vectors": [{"inputs": {"data_in": v}, "expected": {"data_out": (v + 1) & 0xFF}}
                        for v in (0, 1, 254, 255)],
        }, indent=2),
        "golden/golden_report.md": (
            f"# Golden Model — {sc.task_name}\n\n"
            f"Top: `{model_top}`\n\nDeterministic template (no LLM provider configured). "
            "The real run writes one Python model per IP, per sub-toplevel and for the "
            "toplevel, with a test and exported vectors for each.\n"),
        _GOLDEN_CONTRACT_REL: (
            f"# Build contract — {sc.task_name}\n\n"
            "| module | file | tier | role | ports |\n|---|---|---|---|---|\n"
            f"| {model_top} | rtl/{model_top}.v | top | toplevel | clk, rst_n, data_i, data_o |\n"),
    }
    sc.persist(files)
    tests = _run_golden_tests(sc)
    summary = _write_golden_summary(sc, tests)
    files[_GOLDEN_SUMMARY_REL] = json.dumps(summary, indent=2)
    if sc.workspace is not None and (sc.workspace / "golden" / "test_results.json").is_file():
        files["golden/test_results.json"] = (
            sc.workspace / "golden" / "test_results.json").read_text()
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} produced a template golden model for {sc.task_name} "
                f"({tests.get('passed', 0)}/{tests.get('total', 0)} test(s) passing).",
        diagnostics=[_diag(sc.stage, agent, "Golden model (template)",
                           "No LLM provider configured — wrote the deterministic golden-model "
                           "skeleton, its test and its exported vectors.")],
        artifacts=[_artifact("artifact-golden-summary", "golden_summary.json", "GOLDEN", agent,
                             _GOLDEN_SUMMARY_REL),
                   _artifact("artifact-golden-report", "golden_report.md", "REPORT", agent,
                             "golden/golden_report.md")],
        workspace_files=files,
        recommended_next="Review the golden model output, then approve to start RTL_GEN.",
        structured_conclusion={"top_module": model_top, "tests": _tests_summary(tests),
                               "previews": summary.get("previews", []), "awaiting_review": True},
        artifact_refs=list(files.keys()),
    )


def _tests_summary(tests: Dict[str, Any]) -> Dict[str, Any]:
    return {k: tests.get(k) for k in ("ran", "total", "passed", "failed", "files")}


# --------------------------------------------------------------------------- #
# RTL_GEN — deep-agent generation with compile-on-write, rtl_author fallback
# --------------------------------------------------------------------------- #
def _rtl_status(workspace: Path) -> Dict[str, Any]:
    """Compile status of every RTL file on disk + the detected top module.
    ``systemverilog`` lists files that violate the plain-Verilog-2001 contract."""
    rtl_dir = workspace / "rtl"
    status: Dict[str, Any] = {"files": [], "broken": {}, "top": "", "systemverilog": []}
    if not rtl_dir.is_dir():
        return status
    status["systemverilog"] = [p.name for p in sorted(rtl_dir.glob("*.sv"))
                               + sorted(rtl_dir.glob("*.svh"))]
    try:
        from verilog_check import check_file, pick_top
        for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
            status["files"].append(p.name)
            err = check_file(p, rtl_dir)
            if err:
                status["broken"][p.name] = err
        status["top"] = pick_top(rtl_dir) or ""
    except Exception:  # noqa: BLE001
        status["files"] = [p.name for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))]
    return status


def _golden_ips_without_rtl(sc: StageContext) -> List[str]:
    """Golden-contract modules (any tier) that no rtl/*.v module implements.
    Empty when there is no golden contract — pre-GOLDEN_GEN designs are not
    held to a module map that was never written."""
    if sc.workspace is None:
        return []
    golden_ips = _golden_ips(sc)
    if not golden_ips:
        return []
    have = {m.lower() for m in _rtl_hierarchy(sc.workspace).get("modules", {})}
    return [str(ip["name"]) for ip in golden_ips
            if str(ip.get("name", "")).lower() not in have
            and str(ip.get("tier", "")).lower() in ("ip", "subtop", "top")]


def _rtl_structure_gaps(sc: StageContext, status: Dict[str, Any]) -> List[str]:
    """Structural violations of the multi-file contract: SystemVerilog files,
    more than one module in a file, a missing hierarchy tier, or a golden IP
    with no RTL counterpart. These are what turn "one big .sv" into a real
    IP/sub-top/top decomposition."""
    if sc.workspace is None:
        return []
    gaps: List[str] = []
    if status.get("systemverilog"):
        gaps.append("these files are SystemVerilog — the hardening flow's yosys cannot read "
                    "them. Rewrite each as plain Verilog-2001 with a `.v` name "
                    "(rename_file_disk, then convert `logic`→`reg`/`wire`, `always_ff`→"
                    "`always @(posedge clk)`, drop typedefs/structs/interfaces) and update every "
                    "`include/instantiation: " + ", ".join(status["systemverilog"]))
    hierarchy = _rtl_hierarchy(sc.workspace)
    if hierarchy.get("multi_module"):
        gaps.append("ONE MODULE PER FILE is the contract — these files declare several modules; "
                    "split each extra module into its own rtl/<module>.v: "
                    + ", ".join(hierarchy["multi_module"]))
    golden_ips = _golden_ips(sc)
    if golden_ips:
        have = {m.lower() for m in hierarchy.get("modules", {})}
        missing = [ip["name"] for ip in golden_ips
                   if str(ip.get("name", "")).lower() not in have]
        if missing:
            # Distinguish "the file was never written" from "the file exists but
            # declares a differently-named module". Telling the agent to write
            # rtl/sobel_top.v when that file is already on disk is un-actionable,
            # and the repair passes burn out re-reading a file that looks fine.
            by_file = {Path(f).stem.lower(): m
                       for m, f in hierarchy.get("modules", {}).items() if f}
            renames, absent = [], []
            for name in missing:
                declared = by_file.get(str(name).lower())
                (renames if declared else absent).append(
                    f"rtl/{name}.v declares `{declared}` — rename that module to `{name}` "
                    f"(and update every instantiation of `{declared}`)" if declared else name)
            if absent:
                gaps.append("the golden contract defines these IP blocks but no RTL module "
                            "implements them — write rtl/<name>.v for each: " + ", ".join(absent))
            if renames:
                gaps.append("these contracted modules exist as FILES but the module name inside "
                            "does not match the contract, so nothing downstream can find them "
                            "(TB_GEN builds tb/<module>_tb.v from the contract name): "
                            + "; ".join(renames))
        tiers = {str(ip.get("tier", "")).lower() for ip in golden_ips}
        if "subtop" in tiers and not hierarchy.get("subtops"):
            gaps.append("the golden contract has SUB-TOPLEVEL block(s) but every RTL module is "
                        "either a leaf or the top — add the sub-toplevel module(s) that "
                        "instantiate the IPs, and have the top instantiate those.")
    elif len(status.get("files", [])) == 1:
        gaps.append("the whole design is ONE file. Decompose it: one rtl/<ip>.v per leaf IP, a "
                    "sub-toplevel that wires the IPs into a subsystem, and a top that "
                    "instantiates the sub-toplevel(s).")
    return gaps


def _assert_contract_satisfied(sc: StageContext, status: Dict[str, Any],
                               miss: List[str], struct: List[str]) -> None:
    """Fail RTL_GEN when the approved golden contract is still unmet.

    Only enforced when a golden contract actually exists — a run without
    GOLDEN_GEN (no LLM provider, or an older task) keeps the previous
    best-effort behaviour. What is NOT tolerated is a design that the human
    approved as N modules arriving as one stub named after the task: every
    downstream stage, and the per-IP testbenches in particular, are built from
    the contract's module list."""
    golden_ips = _golden_ips(sc)
    if not golden_ips:
        return
    unmet = [g for g in struct if "no RTL module implements them" in g
             or "SUB-TOPLEVEL" in g or "ONE MODULE PER FILE" in g]
    if not unmet and not miss:
        return
    contracted = ", ".join(str(ip.get("name", "?")) for ip in golden_ips)
    raise RuntimeError(
        f"RTL_GEN did not satisfy the approved golden contract. Contracted modules: "
        f"{contracted}. On disk: {', '.join(status.get('files', [])) or '(no .v files)'}. "
        + (f"Planned files never written: {', '.join(miss)}. " if miss else "")
        + (f"Structure violations: {' | '.join(unmet)} " if unmet else "")
        + "The contract in context/golden_contract.md is what the user approved at the "
          "golden gate and what TB_GEN builds per-IP testbenches from, so a partial "
          "implementation cannot be handed downstream. Transcripts: "
          "logs/rtl_gen_deep_agent*.md."
    )


def run_rtl_gen(sc: StageContext) -> AgentResult:
    agent = "RTLAuthor"
    top = sc.top_module

    if _deep_enabled(sc):
        from .deep_agent import PITFALLS
        planned = _planned_rtl_files(sc)
        notes = ""
        dn = sc.workspace / "context" / "design_notes.md"
        if dn.is_file():
            notes = ("\nBUILD CONTRACT: `context/design_notes.md` holds the module map — follow "
                     "it; write EVERY file it lists"
                     + (": " + ", ".join(f"rtl/{f}" for f in planned) if planned else "")
                     + ".\n")
        func_note = ""
        if (sc.workspace / "context" / "chip_input_grid.json").is_file():
            func_note = (
                "\nFUNCTIONAL REQUIREMENT (non-negotiable): the chip implements EXACTLY the "
                "algorithm the golden model implements and must COMPUTE AND OUTPUT the solved "
                "result for the canonical input (context/chip_input_grid.json) — for a "
                "maze/navigation brief, the route from start to goal, observable at the "
                "chip's outputs. The NN weights the golden model derived are already "
                "quantized in rtl/*.mem — LOAD THOSE, never re-train or re-quantize them "
                "here, and never substitute a different algorithm to make the task easier.\n")
        goal = (
            f"Design complete, synthesizable Verilog-2001 for this hardware: {sc.design_brief}\n"
            + _golden_note(sc) +
            "\nHIERARCHY (the shape of the deliverable — a real chip is never one file):\n"
            "  • LEAF IPs — one `rtl/<ip>.v` per functional block (datapath, register file/"
            "buffer, arithmetic unit, activation LUT, control FSM, …), each mirroring the "
            "matching `golden/model/<ip>.py`;\n"
            "  • SUB-TOPLEVEL — `rtl/<subsystem>.v` modules that instantiate and wire the leaf "
            "IPs into a subsystem (one per subsystem in the contract);\n"
            "  • TOPLEVEL — `rtl/<top>.v`, which instantiates the sub-toplevel(s) and exposes "
            "the chip's ports. It contains WIRING, not algorithm.\n"
            "ONE MODULE PER FILE, and the file is named after the module.\n"
            "FILE FORMAT: plain Verilog-2001 `.v` ONLY (headers `.vh`). `.sv`/`.svh` are "
            "REJECTED on write — no `logic`, `always_ff`, typedefs, packed structs or "
            "interfaces; use `reg`/`wire` and `always @(posedge clk or negedge rst_n)`.\n"
            "PORT RULE: module ports must be plain Verilog-2001 packed vectors ONLY. NEVER "
            "use unpacked array ports (`output reg [7:0] q [0:3]`) — iverilog accepts them "
            "but the hardening flow's yosys Verilog-2005 frontend REJECTS them and PNR dies; "
            "flatten to a packed vector (`output reg [4*8-1:0] q_flat`) instead. Unpacked "
            "arrays INSIDE modules (memories) are fine.\n"
            + _digest_note(sc)
            + func_note
            + notes
            + _anchor_note(sc)
            + "Write each file with write_file_disk; a shared header (`rtl/params.vh`) holds "
              "common `define/parameters and `rtl/<name>.mem` holds data. EVERY write of a .v "
              "file returns a COMPILE CHECK result — if it reports errors, FIX that file and "
              "write it again immediately; never leave a file broken.\n"
              "Reference shared macros WITH the backtick (`WIDTH) and `include \"params.vh\" in "
              "every file that uses them.\n"
              "BIT-EXACTNESS: each module must reproduce its golden counterpart's numbers "
              "exactly — same widths, same signedness, same Qm.n format, same rounding/"
              "saturation, same .mem data. Cross-check against golden/vectors/<module>.json as "
              "you write. The data files (LUTs, filter taps, NN weights) were already computed "
              "and quantized by GOLDEN_GEN — reuse rtl/*.mem, do not regenerate them.\n"
              "When every file exists and compiles clean, reply just 'done' — your RTL is the "
              "files on disk; do NOT paste the whole design back.\n"
            + PITFALLS
        )
        # Budget scales with the contract. A flat limit is what truncated a 7-file
        # CGRA after `params.vh`: each module costs a read of its golden
        # counterpart, a write, and usually a compile-error fix, so a fixed 80
        # steps silently caps the design at two or three modules.
        n_modules = max(len(planned), len(_golden_ips(sc)), 3)
        rtl_budget = min(80 + 22 * n_modules, 260)
        _run_deep(sc, goal, "rtl_gen_deep_agent", recursion_limit=rtl_budget)

        # COMPLETENESS GATE (GarudaChip): never report success with broken RTL or
        # with planned modules unwritten. A planned file is satisfied by an exact
        # stem match or a specialized variant (`alu.v` → `alu_8bit.v`). Give the
        # agent focused passes to finish/fix, then report honestly.
        def _missing(status_now) -> List[str]:
            have = {re.sub(r"\.(svh|sv|vh|v|mem)$", "", f).lower() for f in status_now["files"]}
            rtl_dir = sc.workspace / "rtl"
            have |= {p.stem.lower() for p in rtl_dir.glob("*.*")} if rtl_dir.is_dir() else set()
            out = []
            for f in planned:
                stem = re.sub(r"\.(svh|sv|vh|v|mem)$", "", f).lower()
                if any(h == stem or (len(stem) > 2 and h.startswith(stem + "_")) for h in have):
                    continue
                out.append(f)
            return out

        status = _rtl_status(sc.workspace)
        miss = _missing(status)
        struct = _rtl_structure_gaps(sc, status)
        for _pass in range(3):
            if status["files"] and not status["broken"] and not miss and not struct:
                break
            broken_note = "".join(
                f"- FIX rtl/{f} — its compile errors:\n{e[:500]}\n"
                for f, e in status["broken"].items())
            goal2 = (
                f"You are STILL generating RTL for: {sc.design_brief}. "
                f"Already written: {', '.join(status['files']) or '(none)'}.\n"
                + _golden_note(sc)
                + _anchor_note(sc)
                + (("WRITE THE MISSING PLANNED FILES NOW — complete and synthesizable, ONE "
                    "write_file_disk call each, reusing the interfaces in "
                    "context/golden_contract.md and the existing modules. Do NOT rewrite "
                    "working files:\n" + "\n".join(f"- rtl/{f}" for f in miss) + "\n")
                   if miss else "")
                + (("These files FAILED their compile check — read each, fix the exact errors, "
                    "write it back; the write result must say 'compile check clean':\n" + broken_note)
                   if status["broken"] else "")
                + (("STRUCTURE VIOLATIONS — the deliverable must be a multi-file "
                    "IP / sub-toplevel / top decomposition in plain Verilog-2001:\n- "
                    + "\n- ".join(struct) + "\n") if struct else "")
                + ("NO RTL exists yet — write the design's modules to rtl/ NOW, one "
                   "write_file_disk call each.\n" if not status["files"] else "")
                + "STAY ON TASK: your ONLY job in this pass is write_file_disk calls into "
                  "rtl/. Do not re-read golden/tests/ or golden/model/ to re-derive the "
                  "design — the interfaces you need are already in "
                  "context/golden_contract.md. Read a golden file ONLY if you are about to "
                  "write the matching rtl/ module and need its exact widths. Every missing "
                  "file above must exist when you finish.\n"
                + "When every file exists AND compiles clean, reply 'done'.\n" + PITFALLS
            )
            _run_deep(sc, goal2, f"rtl_gen_deep_agent_fix{_pass + 1}",
                      recursion_limit=min(60 + 18 * len(miss or struct or [1]), 200))
            status = _rtl_status(sc.workspace)
            miss = _missing(status)
            struct = _rtl_structure_gaps(sc, status)
        hierarchy = _rtl_hierarchy(sc.workspace)
        _log_state(sc, "generate:done",
                   f"files={status['files']}, broken={list(status['broken']) or 'none'}, "
                   f"planned-missing={miss or 'none'}, ips={hierarchy.get('ips')}, "
                   f"subtops={hierarchy.get('subtops')}, top={hierarchy.get('top')}, "
                   f"structure-gaps={struct or 'none'}")

        # The golden contract is a CONTRACT, not a hint: the user approved that
        # module decomposition at the GOLDEN_GEN gate, and TB_GEN generates one
        # testbench per contracted module from it. Shipping fewer modules than
        # the contract names silently rewrites what was approved, so a still-
        # unsatisfied contract fails the stage instead of reporting success.
        _assert_contract_satisfied(sc, status, miss, struct)

        # A golden IP with no RTL module is not a partial success — it is the
        # contract unmet. Reporting SUCCEEDED here is what let a stub design
        # reach TB_GEN and SIM: the downstream stages then sized their own work
        # to the stub instead of to the contract. Fail where the gap is.
        golden_missing = _golden_ips_without_rtl(sc)
        if golden_missing:
            raise RuntimeError(
                "RTL_GEN did not implement the golden contract: no rtl/<module>.v for "
                f"{', '.join(golden_missing)}. The contract in context/golden_contract.md is "
                "the approved module map — every IP, sub-toplevel and the top get their own "
                f"Verilog-2001 file. Written so far: {', '.join(status['files']) or '(none)'}. "
                f"Transcripts: logs/rtl_gen_deep_agent*.md."
            )

        if status["files"]:
            top = status["top"] or top
            compiled = not status["broken"]
            files = _files_from_disk(sc.workspace, ["rtl"])
            arch = (
                f"# RTL Architecture — {top}\n\n"
                f"Generated for task {sc.task_name} by the RLM deep agent, implementing the "
                "Python golden model in `golden/`.\n\n"
                f"- **Top module:** `{top}`\n"
                f"- **Sub-toplevel(s):** "
                + (", ".join(f"`{m}`" for m in hierarchy.get("subtops", [])) or "_none_") + "\n"
                f"- **Leaf IPs:** "
                + (", ".join(f"`{m}`" for m in hierarchy.get("ips", [])) or "_none_") + "\n"
                f"- **Files:** " + ", ".join(f"`rtl/{f}`" for f in status["files"]) + "\n"
                f"- **Compile check:** " + ("all clean ✓" if compiled else
                                            f"{len(status['broken'])} file(s) still broken: "
                                            + ", ".join(status["broken"])) + "\n"
                f"- **Structure:** " + ("multi-file Verilog-2001, one module per file ✓"
                                        if not struct else "; ".join(struct)) + "\n"
            )
            files["reports/rtl_architecture.md"] = arch
            sc.persist({"reports/rtl_architecture.md": arch})
            artifacts = [_artifact(f"artifact-rtl-{Path(f).stem}", f, "RTL", agent, f"rtl/{f}")
                         for f in status["files"]]
            artifacts.append(_artifact("artifact-rtl-arch", "rtl_architecture.md", "REPORT",
                                       agent, "reports/rtl_architecture.md"))
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} generated {len(status['files'])} Verilog module file(s) for "
                        f"{sc.task_name} — {len(hierarchy.get('ips', []))} IP(s), "
                        f"{len(hierarchy.get('subtops', []))} sub-toplevel(s), top `{top}` "
                        + ("(compile clean)." if compiled else "(compile errors remain)."),
                diagnostics=[_diag(sc.stage, agent, "RTL generation summary",
                                   f"Deep agent wrote {status['files']}; top={top}; "
                                   f"ips={hierarchy.get('ips')}; "
                                   f"subtops={hierarchy.get('subtops')}; "
                                   f"broken={list(status['broken']) or 'none'}; "
                                   f"structure={struct or 'clean'}.",
                                   confidence="Deep agent")],
                artifacts=artifacts,
                workspace_files=files,
                recommended_next=("Validate generated RTL and queue verification stages."
                                  if compiled else "RTL failed compile-check; run RTL_REPAIR."),
                structured_conclusion={
                    "top_module": top,
                    "files": [f"rtl/{f}" for f in status["files"]],
                    "ips": hierarchy.get("ips", []),
                    "subtops": hierarchy.get("subtops", []),
                    "structure_gaps": struct,
                    "compiled": compiled,
                    "provider": "deep-agent",
                },
                artifact_refs=list(files.keys()),
            )
        # deep agent produced nothing usable → fall through to the one-shot path

    # The one-shot author writes a SINGLE rtl/<top>.v from the brief alone. That
    # is a reasonable floor for a contract-less run, but against an approved
    # golden contract it is a silent downgrade: one stub module named after the
    # task, replacing the decomposition the user signed off on. Refuse it.
    if _golden_ips(sc):
        contracted = ", ".join(str(ip.get("name", "?")) for ip in _golden_ips(sc))
        raise RuntimeError(
            "RTL_GEN produced no usable RTL from the golden contract, and the single-file "
            f"fallback author cannot satisfy it (contracted modules: {contracted}). "
            "Writing one rtl/<task>.v stub here would hand a design downstream that the "
            "user never approved. Check logs/rtl_gen_deep_agent*.md for why the deep agent "
            "wrote no modules."
        )

    result = rtl_author.generate_rtl(sc.design_brief, top,
                                     runtime=rtl_author.build_llm_runtime(sc.llm_model))
    top = result.top
    status_label = "compiled cleanly" if result.compiled else "did NOT compile after repair"
    arch = (
        f"# RTL Architecture — {top}\n\n"
        f"Generated for task {sc.task_name} via `{result.provider}`.\n\n"
        f"- **Compile check (iverilog -tnull):** {status_label}\n"
        f"- **Generation attempts:** {result.attempts}"
        + (" (auto-repair engaged)" if result.repaired else "")
        + "\n\n## Top module\n"
        f"- `{top}`\n\n"
        + ("## Applied fix hints\n" + "\n".join(f"- {h[:160]}" for h in result.fix_hints) + "\n\n" if result.fix_hints else "")
        + "## Compile log\n```\n" + (result.log[:2000] or "(none)") + "\n```\n"
    )
    files = {
        f"rtl/{top}.v": result.code if result.code.endswith("\n") else result.code + "\n",
        "reports/rtl_architecture.md": arch,
    }
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated RTL for {sc.task_name} ({result.provider}, {status_label}).",
        diagnostics=[_diag(sc.stage, agent, "RTL generation summary",
                           f"Authored rtl/{top}.v via {result.provider}; compiled={result.compiled}; attempts={result.attempts}.")],
        artifacts=[_artifact("artifact-rtl-top", f"{top}.v", "RTL", agent, f"rtl/{top}.v"),
                   _artifact("artifact-rtl-arch", "rtl_architecture.md", "REPORT", agent,
                             "reports/rtl_architecture.md")],
        workspace_files=files,
        recommended_next=("Validate generated RTL and queue verification stages."
                          if result.compiled else "RTL failed compile-check; run RTL_REPAIR."),
        structured_conclusion={
            "top_module": top,
            "files": list(files.keys()),
            "compiled": result.compiled,
            "attempts": result.attempts,
            "repaired": result.repaired,
            "provider": result.provider,
        },
        artifact_refs=list(files.keys()),
    )


# --------------------------------------------------------------------------- #
# RTL_REPAIR — deep-agent corrector (web fix search + lessons), loop fallback
# --------------------------------------------------------------------------- #
def run_rtl_repair(sc: StageContext) -> AgentResult:
    """Conditional stage: re-run the compile-repair loop on existing RTL."""
    agent = "RTLAuthor"
    top = sc.top_module

    if _deep_enabled(sc):
        from .deep_agent import PITFALLS
        status = _rtl_status(sc.workspace)
        top = status["top"] or top

        # SIMULATION-FAILURE repair: the orchestrator re-dispatches this stage
        # when the self-checking testbench FAILED (not a compile problem). The
        # evidence is the sim log; the deep agent debugs the DESIGN's behaviour.
        sim_log_path = sc.workspace / "logs" / "sim.log"
        sim_failed = ("simulation" in sc.prompt.lower() or "testbench fail" in sc.prompt.lower()
                      or (sim_log_path.is_file()
                          and re.search(r"FAILED|\$fatal|mismatch",
                                        sim_log_path.read_text(errors="replace"), re.I) is not None
                          and not re.search(r"TEST\s+PASSED",
                                            sim_log_path.read_text(errors="replace"), re.I)))
        if not status["broken"] and sim_failed and sim_log_path.is_file():
            sim_tail = sim_log_path.read_text(errors="replace")[-2000:]
            canonical_note = ""
            grid_json = sc.workspace / "context" / "chip_input_grid.json"
            if grid_json.is_file():
                canonical_note = (
                    "\nGROUND TRUTH INPUT: `context/chip_input_grid.json` is the CANONICAL "
                    "chip input (grid, start, goal). BOTH the RTL and the testbench "
                    "expectations must agree with IT — check each side against this file "
                    "first (a tb expectation that contradicts the canonical grid is a tb "
                    "bug; a DUT register that never loads the grid/start/goal is an RTL "
                    "bug, e.g. a wrong $readmemh path or an unwired load).\n"
                    f"Canonical head: {grid_json.read_text()[:400]}\n")
            goal = (
                f"The design compiles but its SELF-CHECKING TESTBENCH FAILED in simulation "
                f"(design: {sc.design_brief}; top `{top}`).\n"
                f"SIMULATION LOG (tail):\n{sim_tail}\n"
                + canonical_note
                + _golden_note(sc) +
                "\nDebug the CHIP'S BEHAVIOUR from the design's own evidence:\n"
                "1. Read the failing vectors in the log — which expected vs. actual mismatched;\n"
                "2. run the APPROVED Python golden model in `golden/` (run_python) on those same "
                "inputs to get the correct values — it is the reference, so never edit it to "
                "match the RTL;\n"
                "3. grep_files/read_file_disk the responsible module(s) and find the logic bug "
                "(off-by-one, wrong signedness, missing pipeline stage, reset value, wrong "
                "$readmemh path — mem paths are workspace-root-relative like rtl/x.mem, …);\n"
                "4. Fix the RTL (or the testbench IF its expectation was computed wrongly — "
                "the golden model decides which is wrong) and write it back compile-clean;\n"
                "5. VERIFY YOUR FIX YOURSELF before finishing: run_python "
                "`import subprocess; print(subprocess.run(['sh','-c','iverilog -g2012 -o work/re.vvp "
                "-Irtl -s " + f"{top}_tb" + " rtl/*.v tb/" + f"{top}_tb" + ".* && vvp work/re.vvp'], "
                "capture_output=True, text=True).stdout[-3000:])` and CHECK it prints TEST "
                "PASSED. Iterate until it does or you are certain of the remaining blocker.\n"
                "Do NOT weaken the testbench to make it pass — the golden model and the "
                "canonical input are the truth. Do NOT redefine the DESIRED OUTPUT to "
                "dodge the failure (e.g. 'the agent never reaches the goal, so the output "
                "is the unchanged grid') — the desired output IS the solved route (path "
                "cells marked 4) produced by THE ALGORITHM THE BRIEF SPECIFIES. If the RTL "
                "cannot reach the goal, fix the RTL's implementation of that algorithm, or "
                "TRAIN/DERIVE better weights in Python and update the rtl/*.mem files (the "
                "golden model must use the same weights and fixed-point math) — never swap "
                "in a different algorithm. NEVER remove the testbench's required "
                "deliverables: $dumpfile(\"design.vcd\")+$dumpvars AND the chip-output dump "
                "($writememh(\"waves/chip_output.mem\", …) of the DUT's result) must stay in "
                "(or be ADDED to) the tb — SIM fails without them. Reply 'done' only after "
                "your own re-run passes (or state exactly what still fails and why).\n" + PITFALLS
            )
            _run_deep(sc, goal, "rtl_repair_deep_agent", recursion_limit=90)
            status = _rtl_status(sc.workspace)
            files = _files_from_disk(sc.workspace, ["rtl", "tb"])
            note = (f"# RTL Repair (simulation failure) — {top}\n\n"
                    f"- Debugged the failing testbench run; files now: {', '.join(status['files'])}\n"
                    f"- Compile clean: {'yes' if not status['broken'] else 'no'}\n")
            files["reports/rtl_repair.md"] = note
            sc.persist({"reports/rtl_repair.md": note})
            _log_state(sc, "repair:sim-failure",
                       f"debugged failing simulation; broken={list(status['broken']) or 'none'}")
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} debugged the failing simulation for {top} (deep agent).",
                diagnostics=[_diag(sc.stage, agent, "Simulation-failure repair",
                                   "Deep agent debugged the failing testbench run against a "
                                   "golden model and rewrote the faulty logic.",
                                   confidence="Deep agent")],
                artifacts=[_artifact("artifact-rtl-repair", "rtl_repair.md", "REPORT", agent,
                                     "reports/rtl_repair.md")],
                workspace_files=files,
                recommended_next="Re-run SIM to confirm the fix.",
                structured_conclusion={"top_module": top, "compiled": not status["broken"],
                                       "repaired": True, "mode": "simulation"},
                artifact_refs=list(files.keys()),
            )

        # HARDENING / EXPLICIT repair: the orchestrator (or an operator) sent a
        # substantive repair instruction that is NOT a sim failure — e.g.
        # "LibreLane produced no GDS: flatten the unpacked array port". The old
        # code fell through to "already compile-clean" and silently did NOTHING,
        # which is why PNR auto-repair rounds never fixed anything.
        explicit = (sc.prompt or "").strip()
        harden_failed = any(k in explicit.lower() for k in
                            ("hardening", "librelane", "no gds", "synthesiz", "yosys"))
        if not status["broken"] and (harden_failed or len(explicit) >= 180):
            goal = (
                f"REPAIR INSTRUCTION for design `{top}` ({sc.design_brief}):\n{explicit}\n\n"
                "The RTL already compiles with iverilog and the testbench PASSES — keep it "
                "that way. Apply EXACTLY the fix described above (write_file_disk enforces "
                "the hardening/golden contracts and will reject wrong shapes). VERIFY "
                "YOURSELF before finishing: run_python "
                "`import subprocess; print(subprocess.run(['sh','-c','iverilog -g2012 -o work/re.vvp "
                "-Irtl -s " + f"{top}_tb" + " rtl/*.v tb/" + f"{top}_tb" + ".* && vvp work/re.vvp'], "
                "capture_output=True, text=True).stdout[-3000:])` and CHECK it prints TEST "
                "PASSED. Reply 'done' only after your own re-run passes.\n" + PITFALLS)
            _run_deep(sc, goal, "rtl_repair_deep_agent", recursion_limit=90)
            status = _rtl_status(sc.workspace)
            files = _files_from_disk(sc.workspace, ["rtl", "tb"])
            note = (f"# RTL Repair (hardening/explicit) — {top}\n\n"
                    f"- Applied targeted repair; files now: {', '.join(status['files'])}\n"
                    f"- Compile clean: {'yes' if not status['broken'] else 'no'}\n")
            files["reports/rtl_repair.md"] = note
            sc.persist({"reports/rtl_repair.md": note})
            _log_state(sc, "repair:hardening",
                       f"targeted repair applied; broken={list(status['broken']) or 'none'}")
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} applied a targeted (hardening) repair for {top} (deep agent).",
                diagnostics=[_diag(sc.stage, agent, "Hardening repair",
                                   "Deep agent applied the targeted synthesizability/contract fix.",
                                   confidence="Deep agent")],
                artifacts=[_artifact("artifact-rtl-repair", "rtl_repair.md", "REPORT", agent,
                                     "reports/rtl_repair.md")],
                workspace_files=files,
                recommended_next="Re-run SIM, then SYNTH/PNR.",
                structured_conclusion={"top_module": top, "compiled": not status["broken"],
                                       "repaired": True, "mode": "hardening"},
                artifact_refs=list(files.keys()),
            )

        if not status["broken"]:
            note = (f"# RTL Repair — {top}\n\n- **Compile clean:** yes\n"
                    f"- Files: {', '.join(status['files']) or '(none)'}\n")
            files = {"reports/rtl_repair.md": note}
            sc.persist(files)
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} ran RTL repair for {top}: already compile-clean.",
                diagnostics=[_diag(sc.stage, agent, "RTL repair", "All RTL files compile clean.",
                                   confidence="Deep agent")],
                artifacts=[_artifact("artifact-rtl-repair", "rtl_repair.md", "REPORT", agent,
                                     "reports/rtl_repair.md")],
                workspace_files=files,
                recommended_next="RTL already clean; continue the DAG.",
                structured_conclusion={"top_module": top, "compiled": True, "rounds": 0,
                                       "repaired": False},
                artifact_refs=list(files.keys()),
            )
        # recall stored lessons for the first broken file's error up-front
        lesson = ""
        try:
            from lessons import error_signature, recall_fix
            first_err = next(iter(status["broken"].values()))
            lesson = recall_fix(error_signature(first_err))
        except Exception:  # noqa: BLE001
            lesson = ""
        broken_note = "".join(f"- rtl/{f}:\n{e[:600]}\n" for f, e in status["broken"].items())
        goal = (
            f"REPAIR the RTL of this design: {sc.design_brief}\n"
            f"These files FAIL their compile check:\n{broken_note}\n"
            + (f"REMEMBERED LESSON from a past run:\n{lesson[:1200]}\n" if lesson else "")
            + "For each broken file: read_file_disk it, understand the exact error, fix it, and "
              "write it back — the write result must say 'compile check clean'. If an error is "
              "unfamiliar, search_web the error message for the correct code pattern and "
              "recall_memory for a stored lesson. Do NOT rewrite files that already compile.\n"
              "When every file compiles clean, reply 'done'.\n" + PITFALLS
        )
        _run_deep(sc, goal, "rtl_repair_deep_agent", recursion_limit=60)
        status = _rtl_status(sc.workspace)
        ok = not status["broken"]
        _log_state(sc, "repair:done", f"compile clean={ok}; broken={list(status['broken']) or 'none'}")
        files = _files_from_disk(sc.workspace, ["rtl"])
        note = (
            f"# RTL Repair — {top}\n\n"
            f"- **Compile clean:** {'yes' if ok else 'no'}\n"
            f"- **Still broken:** {', '.join(status['broken']) or 'none'}\n"
        )
        files["reports/rtl_repair.md"] = note
        sc.persist({"reports/rtl_repair.md": note})
        return AgentResult(
            agent_name=agent,
            summary=f"{agent} ran deep-agent RTL repair for {top}: compile_clean={ok}.",
            diagnostics=[_diag(sc.stage, agent, "RTL repair",
                               f"compiled={ok}; still broken={list(status['broken']) or 'none'}.",
                               confidence="Deep agent")],
            artifacts=[_artifact("artifact-rtl-repair", "rtl_repair.md", "REPORT", agent,
                                 "reports/rtl_repair.md")],
            workspace_files=files,
            recommended_next="Re-run SIM/LINT on the repaired RTL." if ok
            else "RTL still failing compile; inspect logs/rtl_repair_deep_agent.md.",
            structured_conclusion={"top_module": top, "compiled": ok,
                                   "repaired": True, "broken": list(status["broken"])},
            artifact_refs=list(files.keys()),
        )

    code = ""
    rtl_rel = f"rtl/{top}.sv"
    if sc.workspace is not None:
        candidate = sc.workspace / "rtl" / f"{top}.sv"
        if candidate.is_file():
            code = candidate.read_text(encoding="utf-8")
        else:
            for existing in sorted((sc.workspace / "rtl").glob("*.*")):
                if existing.suffix.lower() in (".v", ".sv"):
                    code = existing.read_text(encoding="utf-8")
                    top = existing.stem
                    rtl_rel = f"rtl/{existing.name}"
                    break

    ok, log = rtl_author.compile_check({f"{top}.sv": code}) if code else (True, "no RTL found")
    repaired = False
    attempts = 0
    if code and not ok:
        runtime = rtl_author.build_llm_runtime(sc.llm_model)
        max_iters = rtl_author._max_repairs()
        while not ok and attempts < max_iters and not runtime.is_mock:
            hints = rtl_author.knowledge.lookup_fix_hints(log)
            code = rtl_author._repair_rtl(runtime, code, top, log, hints)
            ok, log = rtl_author.compile_check({f"{top}.sv": code})
            attempts += 1
            repaired = True

    files = {rtl_rel: code} if (code and repaired) else {}
    note = (
        f"# RTL Repair — {top}\n\n"
        f"- **Compile clean:** {'yes' if ok else 'no'}\n"
        f"- **Repair rounds:** {attempts}\n\n## Compile log\n```\n{log[:2000]}\n```\n"
    )
    files["reports/rtl_repair.md"] = note
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} ran RTL repair for {top}: compile_clean={ok}, rounds={attempts}.",
        diagnostics=[_diag(sc.stage, agent, "RTL repair", f"compiled={ok}; rounds={attempts}.")],
        artifacts=[_artifact("artifact-rtl-repair", "rtl_repair.md", "REPORT", agent,
                             "reports/rtl_repair.md")],
        workspace_files=files,
        recommended_next="Re-run SIM/LINT on the repaired RTL." if repaired else "RTL already clean; continue the DAG.",
        structured_conclusion={"top_module": top, "compiled": ok, "rounds": attempts, "repaired": repaired},
        artifact_refs=list(files.keys()),
    )


# --------------------------------------------------------------------------- #
# TB_GEN — deep-agent testbench author, templated fallback
# --------------------------------------------------------------------------- #
def run_tb_gen(sc: StageContext) -> AgentResult:
    """TB_GEN — one self-checking Verilog-2001 testbench PER MODULE.

    The golden model has already been approved by the user, so verification is
    no longer guesswork: every leaf IP, every sub-toplevel and the toplevel gets
    its own `tb/<module>_tb.v` whose expected values come from that module's
    `golden/vectors/<module>.json`. A module without a testbench is unverified,
    and a testbench whose expectations were invented rather than taken from the
    golden model proves nothing."""
    agent = "Verifier"
    top = sc.top_module
    rtl_code = ""
    if sc.workspace is not None:
        candidate = sc.workspace / "rtl" / f"{top}.v"
        if candidate.is_file():
            rtl_code = candidate.read_text(encoding="utf-8")
        else:
            for existing in sorted((sc.workspace / "rtl").glob("*.*")):
                if existing.suffix.lower() in (".v", ".sv"):
                    rtl_code = existing.read_text(encoding="utf-8")
                    top = existing.stem
                    break

    if _deep_enabled(sc):
        status = _rtl_status(sc.workspace)
        top = status["top"] or top
        tb_rel = f"tb/{top}_tb.v"
        hierarchy = _rtl_hierarchy(sc.workspace)
        # EVERY design module needs its own unit testbench — leaf IPs first,
        # then the sub-toplevels that integrate them, then the top.
        #
        # The list is driven by the GOLDEN CONTRACT, not by whatever happens to
        # be in rtl/ right now. Deriving it from the RTL hierarchy alone made
        # coverage collapse to the toplevel whenever RTL_GEN was incomplete: a
        # stub rtl/ yields no IPs, so "every module is covered" was vacuously
        # true and TB_GEN passed with one testbench. The golden model defines
        # the IP set; the RTL has to answer for it either way.
        vector_modules = _golden_vector_modules(sc)
        contract_units = [str(ip.get("name", "")) for ip in _golden_ips(sc)
                          if str(ip.get("tier", "")).lower() in ("ip", "subtop")
                          and str(ip.get("name", ""))]
        unit_modules: List[str] = []
        for m in (contract_units
                  + [m for m in vector_modules if m != top]
                  + [m for m in hierarchy.get("ips", [])]
                  + [m for m in hierarchy.get("subtops", [])]):
            if m and m != top and m not in unit_modules:
                unit_modules.append(m)
        unit_modules = unit_modules[:16]
        unit_note = ""
        if unit_modules:
            with_vectors = [m for m in unit_modules if m in vector_modules]
            without = [m for m in unit_modules if m not in vector_modules]
            unit_note = (
                "\nPER-IP VERIFICATION — write ONE unit testbench per module, "
                "`tb/<module>_tb.v` (plain Verilog-2001), for EVERY module below. Each "
                "instantiates JUST that module, drives its clock/reset and inputs, checks "
                "EVERY output against the expected value ($display the vector as "
                "'vec N: in=… expected=… actual=…', $fatal on mismatch), prints "
                "'<module> TEST PASSED' and $finish-es. An IP that is not checked against "
                "known-correct values is NOT verified:\n"
                + "".join(f"  - tb/{m}_tb.v ← expected values from golden/vectors/{m}.json\n"
                          for m in with_vectors)
                + "".join(f"  - tb/{m}_tb.v ← NO golden vectors on file: read "
                          f"golden/model/{m}.py, run it with run_python on your chosen "
                          "stimulus to COMPUTE the expected outputs, and use those\n"
                          for m in without)
                + "Read each JSON with read_file_disk and BAKE its vectors into the "
                  "testbench as literals (or a tb-local $readmemh .mem) — the numbers in the "
                  "vectors file are the contract; never round, rescale or 'fix' them.\n")
        # INFERENCE CONTRACT: only images the vision triage classified as
        # CHIP-INPUT DATA are fed to the chip; an architecture diagram is never
        # turned into pixels. The stimulus and the desired output were both
        # produced by GOLDEN_GEN — the testbench consumes them, it does not
        # re-derive them.
        data_images = _chip_data_images(sc)
        infer_note = ""
        if data_images or any(f.endswith(".mem") for f in status["files"]):
            infer_note = (
                "\nCHIP INPUT/OUTPUT: the canonical stimulus (`rtl/*.mem`, "
                "`context/chip_input_grid.json`) and the DESIRED result "
                "(`waves/golden_output.mem`) were computed by the approved golden model. "
                "REUSE THEM EXACTLY — do NOT re-derive the input from the uploaded image and "
                "do NOT recompute or overwrite waves/golden_output.mem (a testbench that "
                "writes its own golden is comparing the chip against its own fabrication and "
                "is rejected on write).\n"
                "The MAIN testbench must DUMP the chip's computed RESULT with $writememh into "
                "`waves/chip_output.mem` — EXACTLY the same format and order as "
                "golden_output.mem — and $display the key output values. The output must come "
                "from the DUT's ports/memory, never copied from the golden data. Size the "
                "result registers for the FULL value range (a grid holding 0..4 needs "
                "`reg [2:0]`; `reg [1:0]` silently truncates 4 to 0 and fakes a pass).\n"
                "SIM then compares chip_output.mem against golden_output.mem value by value "
                "and FAILS on any mismatch — the chip is only correct when "
                "input → RTL output equals input → golden output.\n")
        goal = (
            f"Write SELF-CHECKING Verilog-2001 testbenches for this design (top module "
            f"`{top}`; design intent: {sc.design_brief}).\n"
            + _golden_note(sc) +
            "\nFILE FORMAT: every testbench is a plain `.v` file under `tb/` — one testbench "
            "per module, named `tb/<module>_tb.v`. `.sv` is REJECTED on write; use "
            "`reg`/`wire`, `always @(posedge clk)`, `integer` loops, and `$fatal`/`$display`.\n"
            "First read_file_disk the top module (and grep_files each submodule's port list) "
            f"so every connection is EXACT. Write the MAIN testbench to `{tb_rel}`: "
            f"instantiate `{top}` as `dut`, drive a clock and reset, apply the canonical "
            "stimulus, CHECK the outputs against the golden model's expected values "
            "($fatal/$error on mismatch, $display \"TEST PASSED\" on success), dump waves with "
            "$dumpfile(\"design.vcd\") + $dumpvars, and end with $finish.\n"
            + unit_note
            + infer_note
            + "VERIFIABILITY IS THE CONTRACT: every checked value must come from the approved "
              "golden model — golden/vectors/<module>.json for the units, "
              "waves/golden_output.mem (and golden/model/top.py) for the toplevel. A testbench "
              "that only toggles inputs, checks 'output changed', or invents its own "
              "expectations proves nothing. On mismatch, $display the failing vector (inputs, "
              "expected, actual) so the repair stage can act on it.\n"
              "Each write result compiles the tb WITH its DUT — if it reports errors, fix and "
              "rewrite until clean. When the main testbench AND every unit testbench compile "
              "clean, reply 'done'."
        )
        # One testbench per IP plus the toplevel, each with a write + compile-fix
        # round trip. A flat 80 was sized for "main tb only" and silently starved
        # the per-IP set the moment coverage started following the contract.
        tb_budget = min(80 + 22 * max(len(unit_modules), 1), 260)
        _run_deep(sc, goal, "tb_gen_deep_agent", recursion_limit=tb_budget)

        # DETERMINISTIC deliverable check — coverage (a tb per module) and the
        # main tb's required dumps. Asking is not enough: a missing unit tb or a
        # missing dump previously slipped through and failed a later stage.
        tb_dir = sc.workspace / "tb"
        tb_path = sc.workspace / tb_rel
        needs_output = bool(data_images) or any(f.endswith(".mem") for f in status["files"])
        for _fix in range(3):
            missing: List[str] = []
            if not tb_path.is_file():
                # A `.sv` main tb from an older run: ask for the `.v` rewrite.
                legacy = sc.workspace / "tb" / f"{top}_tb.sv"
                missing.append(
                    f"the MAIN testbench `{tb_rel}` does not exist"
                    + (f" (there is a legacy `tb/{top}_tb.sv` — rewrite it as plain "
                       "Verilog-2001 at the .v path and delete_file_disk the .sv)"
                       if legacy.is_file() else "")
                    + " — write it now")
            uncovered = [m for m in unit_modules if not (tb_dir / f"{m}_tb.v").is_file()]
            if uncovered:
                missing.append(
                    "these modules have NO unit testbench — write tb/<module>_tb.v for each, "
                    "with expected values from golden/vectors/<module>.json (or computed by "
                    f"running golden/model/<module>.py): {', '.join(uncovered)}")
            stray = sorted(p.name for p in tb_dir.glob("*.sv")) if tb_dir.is_dir() else []
            if stray:
                missing.append("these testbenches are SystemVerilog — rewrite each as plain "
                               "Verilog-2001 `.v` and delete the `.sv`: " + ", ".join(stray))
            if tb_path.is_file():
                tb_text = tb_path.read_text(errors="replace")
                if "$dumpfile" not in tb_text:
                    missing.append('waveform dump in the main tb: $dumpfile("design.vcd"); '
                                   f"$dumpvars(0, {top}_tb);")
                if needs_output and "$writememh" not in tb_text:
                    missing.append('chip-output dump in the main tb: '
                                   '$writememh("waves/chip_output.mem", <result array>);')
                if re.search(r"\$writememh\s*\(\s*\"[^\"]*golden", tb_text):
                    missing.append("REMOVE the testbench's $writememh of waves/golden_output.mem "
                                   "— the desired output comes from the approved Python golden "
                                   "model, never from the testbench")
            weak = [p.name for p in sorted(tb_dir.glob("*_tb.v"))
                    if not re.search(r"\$fatal|\$error|\$stop", p.read_text(errors="replace"))] \
                if tb_dir.is_dir() else []
            if weak:
                missing.append("these testbenches never FAIL on a wrong value ($fatal/$error is "
                               "absent) — add a real per-vector check: " + ", ".join(weak))
            golden_path = sc.workspace / "waves" / "golden_output.mem"
            if needs_output and not golden_path.is_file():
                missing.append("waves/golden_output.mem is missing — it is a GOLDEN_GEN "
                               "deliverable that SIM compares against. Re-run the approved "
                               "toplevel model (golden/model/top.py) on the canonical input "
                               "with run_python and write it (same N*N row-major hex format as "
                               "the input mem); do not invent a different desired output")
            if not missing:
                break
            _run_deep(sc,
                      "The testbench set is INCOMPLETE. Fix exactly these, change nothing that "
                      "already works, and keep every file compile-clean:\n- "
                      + "\n- ".join(missing) + "\nReply 'done' when they are all satisfied.",
                      f"tb_gen_deep_agent_deliverables{_fix + 1}",
                      recursion_limit=min(45 + 18 * len(missing), 200))

        if tb_path.is_file():
            clean = True
            broken_tbs: List[str] = []
            try:
                from verilog_check import check_tb
                for p in sorted(tb_dir.glob("*_tb.v")):
                    if check_tb(p, sc.workspace / "rtl"):
                        broken_tbs.append(p.name)
                clean = not check_tb(tb_path, sc.workspace / "rtl")
            except Exception:  # noqa: BLE001
                pass
            files = _files_from_disk(sc.workspace, ["tb"])
            tb_names = sorted(Path(p).name for p in files if p.endswith((".v", ".sv")))
            covered = [m for m in unit_modules if (tb_dir / f"{m}_tb.v").is_file()]
            uncovered = [m for m in unit_modules if m not in covered]
            _log_state(sc, "testbench:done",
                       f"testbenches={tb_names}; unit coverage={len(covered)}/"
                       f"{len(unit_modules)}; uncovered={uncovered or 'none'}; "
                       f"top tb clean={clean}")

            # An IP with golden vectors but no testbench is an IP nobody checked
            # against the approved reference. Reporting that as a successful
            # TB_GEN sends SIM off to verify a design whose blocks were never
            # verified, so leave the failure where it happened.
            unchecked = [m for m in uncovered if m in vector_modules]
            if unchecked:
                raise RuntimeError(
                    "TB_GEN left contracted modules unverified: no tb/<module>_tb.v for "
                    f"{', '.join(unchecked)}, although golden/vectors/ holds their approved "
                    "expected values. Every module in the golden contract gets a unit "
                    "testbench built from its vectors. Transcripts: "
                    "logs/tb_gen_deep_agent*.md."
                )
            artifacts = [_artifact(f"artifact-tb-{Path(p).stem}", Path(p).name, "TESTBENCH",
                                   agent, p)
                         for p in sorted(files) if p.endswith((".v", ".sv"))]
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} generated {len(artifacts)} Verilog testbench(es) for {top} — "
                        f"{len(covered)}/{len(unit_modules) or 1} module(s) unit-tested against "
                        "the golden vectors "
                        + ("(compile clean)." if clean else "(compile errors remain)."),
                diagnostics=[_diag(sc.stage, agent, "Testbench generation",
                                   f"Authored {', '.join(tb_names)}. Unit coverage: "
                                   f"{', '.join(covered) or 'none'}"
                                   + (f"; UNCOVERED: {', '.join(uncovered)}" if uncovered else "")
                                   + f". Golden vectors used: {', '.join(vector_modules) or 'none'}"
                                   + f". Top tb clean={clean}"
                                   + (f"; failing tb compile: {', '.join(broken_tbs)}"
                                      if broken_tbs else "") + ".",
                                   confidence="Deep agent")],
                artifacts=artifacts,
                workspace_files=files,
                recommended_next="Review verification notes and move into the next scheduled EDA stage.",
                structured_conclusion={"testbench": tb_rel, "testbenches": tb_names,
                                       "unit_covered": covered, "unit_uncovered": uncovered,
                                       "golden_vectors": vector_modules,
                                       "broken": broken_tbs, "compiled": clean},
                artifact_refs=list(files.keys()),
            )
        # deep agent didn't produce the tb → fall through

    tb = rtl_author.generate_tb(rtl_code, top, sc.design_brief,
                                runtime=rtl_author.build_llm_runtime(sc.llm_model))
    files = {f"tb/{top}_tb.v": tb if tb.endswith("\n") else tb + "\n"}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated a self-checking testbench for {top}.",
        diagnostics=[_diag(sc.stage, agent, "Testbench generation", f"Authored tb/{top}_tb.v with waveform dump and self-check.")],
        artifacts=[_artifact("artifact-tb", f"{top}_tb.v", "TESTBENCH", agent, f"tb/{top}_tb.v")],
        workspace_files=files,
        recommended_next="Review verification notes and move into the next scheduled EDA stage.",
        structured_conclusion={"testbench": f"tb/{top}_tb.v"},
        artifact_refs=list(files.keys()),
    )


def run_signoff(sc: StageContext) -> AgentResult:
    agent = "FlowAssistant"
    ctx = collect_evidence(sc.task_id, sc.workspace, sc.context, sc.eda_reports, sc.reference_files) if sc.workspace else None
    metrics = ctx.metrics if ctx else {}
    signoff = ctx.signoff if ctx else {}
    tapeout_ready = ctx.tapeout_ready if ctx else False
    failed = signoff.get("failed", []) if isinstance(signoff, dict) else []
    approval = [
        f"Timing (WNS): {metrics.get('wns_ns', 'n/a')}",
        f"DRC/LVS clean: {'yes' if not failed else 'no'}",
        f"Tapeout ready: {'yes' if tapeout_ready else 'no'}",
    ]
    md = (
        f"# Signoff Summary — {sc.task_name}\n\n"
        f"- **Tapeout ready:** {'✅' if tapeout_ready else '⚠️ no'}\n"
        f"- **Failed checks:** {', '.join(failed) if failed else 'none'}\n\n"
        "## Metrics\n" + ("\n".join(f"- {k}: {v}" for k, v in metrics.items()) or "- _none_") + "\n\n"
        "## Approval checklist\n" + "\n".join(f"- {a}" for a in approval) + "\n"
    )
    files = {"reports/signoff_summary.md": md}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} converted EDA metrics into a signoff summary for {sc.task_name}.",
        diagnostics=[_diag(sc.stage, agent, "Signoff evaluation", f"Tapeout ready: {tapeout_ready}; failed: {failed or 'none'}.")],
        artifacts=[_artifact("artifact-signoff", "signoff_summary.md", "REPORT", agent,
                             "reports/signoff_summary.md")],
        workspace_files=files,
        recommended_next="Confirm orchestrator approval and continue to EXPORT.",
        structured_conclusion={"tapeout_ready": tapeout_ready, "failed": failed, "metrics": metrics},
        artifact_refs=list(files.keys()),
    )


def _author_module_math(sc: StageContext) -> None:
    """Write `golden/module_math.json` at EXPORT time when it is missing.

    EXPORT owns the IEEE paper, so it must be able to produce every section of
    it from what is already on disk — the golden model, the build contract and
    the RTL are all present by now. Deriving the mathematics here (instead of
    only at GOLDEN_GEN) means refreshing the paper never requires re-running the
    deep model agent and re-opening the human approval gate. Best-effort: the
    report simply omits the section if this cannot run."""
    if sc.workspace is None or (sc.workspace / _GOLDEN_MATH_REL).is_file():
        return
    if not _deep_enabled(sc):
        return
    goal = (
        "Write the engineering explanation the final IEEE paper renders, as the single "
        f"JSON file `{_GOLDEN_MATH_REL}`.\n\n"
        "READ FIRST (they are the ground truth — do not guess): the Python reference model "
        "under `golden/model/`, the build contract `context/golden_contract.md`, and the "
        "Verilog in `rtl/`.\n\n"
        "SCHEMA: {\"algorithm\": {\"summary\": \"2-4 sentences on what the chip computes\", "
        "\"equations\": [\"...\"]}, \"modules\": [{\"name\": \"<rtl module name>\", "
        "\"purpose\": \"2-3 sentences: what it computes and why it exists\", \"io\": "
        "\"key ports in -> out\", \"equations\": [\"...\"]}]}\n\n"
        "Cover EVERY module that has a file in `rtl/`. Each entry of an \"equations\" list "
        "is a LaTeX math BODY ONLY — no dollar signs and no \\begin{equation} wrapper, the "
        "report adds those. Use the real mathematics the golden model implements (for a "
        "Sobel operator: the two 3x3 kernels and the gradient magnitude; plus the actual "
        "fixed-point format and any saturation/rounding the code performs). NEVER state "
        "mathematics the code does not implement — if a module is pure control or storage, "
        "give it an empty \"equations\" list and describe its FSM/addressing instead. "
        "Write the file with write_artifact and reply 'done'."
    )
    try:
        _run_deep(sc, goal, "export_paper_deep_agent", recursion_limit=40)
    except Exception:  # noqa: BLE001 - the paper is still worth producing without it
        pass


def run_export(sc: StageContext) -> AgentResult:
    agent = "FlowAssistant"
    # Authored before evidence collection so the fresh file is picked up in the
    # same run — otherwise the section would only appear on the NEXT export.
    _author_module_math(sc)
    if sc.workspace is not None:
        ctx = collect_evidence(sc.task_id, sc.workspace, sc.context, sc.eda_reports, sc.reference_files)
    else:
        from reporting.evidence import ReportContext

        ctx = ReportContext(task_id=sc.task_id, task_name=sc.task_name, design_brief=sc.design_brief, top_module=sc.top_module)
    files = generate_reports(ctx)
    # Full IEEE Access design report (spec → golden model → GDS, with figures
    # and the LibreLane parameter table). The vendored class files and the Chip
    # Orchestra header artwork are staged next to the .tex, then pdflatex runs
    # twice so the paper itself — not just its source — is a deliverable.
    latex_rel = None
    ieee_pdf_rel = None
    try:
        from reporting.latex_report import compile_pdf, generate_latex, stage_template_assets
        workspace_files = wsfiles.list_files(sc.workspace) if sc.workspace else []
        files["exports/final_report.tex"] = generate_latex(ctx, workspace_files)
        latex_rel = "exports/final_report.tex"
        if sc.workspace is not None:
            sc.persist({latex_rel: files[latex_rel]})
            stage_template_assets(sc.workspace / "exports")
            pdf = compile_pdf(sc.workspace / "exports" / "final_report.tex")
            if pdf is not None:
                ieee_pdf_rel = str(pdf.relative_to(sc.workspace))
    except Exception:  # noqa: BLE001 - LaTeX report is best-effort
        pass
    sc.persist(files)
    pdf_rel = None
    # The reportlab builder writes the SAME path the LaTeX compile just produced
    # (exports/final_report.pdf), and it used to run unconditionally right after
    # — silently overwriting the IEEE Access paper with the plain layout on every
    # single run. It is a FALLBACK for when pdflatex is unavailable or the
    # compile failed, so it only runs when there is no IEEE PDF to preserve.
    if sc.workspace is not None and ieee_pdf_rel is None:
        pdf_rel = generate_pdf(sc.workspace, ctx)
    artifact_refs = list(files.keys())
    artifacts = [
        _artifact("artifact-final-report", "final_design_report.md", "REPORT", agent,
                  next((p for p in files if p.endswith("final_design_report.md")), "")),
        _artifact("artifact-runbook", "runbook.md", "RUNBOOK", agent,
                  next((p for p in files if p.endswith("runbook.md")), "")),
        _artifact("artifact-architecture", "architecture_overview.md", "ARCHITECTURE", agent,
                  next((p for p in files if p.endswith("architecture_overview.md")), "")),
    ]
    if latex_rel:
        artifacts.append(_artifact("artifact-latex", "final_report.tex", "REPORT", agent,
                                   latex_rel))
    if ieee_pdf_rel:
        artifact_refs.append(ieee_pdf_rel)
        artifacts.append(_artifact("artifact-ieee-pdf", "final_report.pdf (IEEE Access)",
                                   "REPORT", agent, ieee_pdf_rel))
    if pdf_rel:
        artifact_refs.append(pdf_rel)
        artifacts.append(_artifact("artifact-pdf", "final_report.pdf", "REPORT", agent, pdf_rel))
    built = ["the final report", "runbook", "architecture overview"]
    if ieee_pdf_rel:
        built.append("the IEEE Access paper (compiled PDF)")
    elif latex_rel:
        built.append("the IEEE Access paper source (.tex — pdflatex unavailable)")
    if pdf_rel:
        built.append("the bundled PDF")
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} assembled " + ", ".join(built[:-1]) + f" and {built[-1]} for "
                f"{sc.task_name}.",
        diagnostics=[_diag(sc.stage, agent, "Report assembly",
                           "Generated evidence-backed markdown reports"
                           + (", compiled the IEEE Access paper to PDF" if ieee_pdf_rel
                              else ", wrote the IEEE Access .tex (pdflatex not available "
                                   "to compile it here)" if latex_rel else "")
                           + (" and a bundled PDF." if pdf_rel else "."))],
        artifacts=artifacts,
        workspace_files=files,
        recommended_next="Publish the final report and close out the task.",
        structured_conclusion={"reports": list(files.keys()), "pdf": pdf_rel,
                              "latex": latex_rel, "ieee_pdf": ieee_pdf_rel,
                              "tapeout_ready": ctx.tapeout_ready},
        artifact_refs=artifact_refs,
    )


def run_fallback(sc: StageContext) -> AgentResult:
    agent = str(sc.context.get("agent_name", "FlowAssistant"))
    note = f"# {sc.stage} notes\n\n{agent} handled stage {sc.stage} for task {sc.task_name}.\n\nPrompt: {sc.prompt}\n"
    rel = f"reports/{sc.stage.lower()}_notes.md"
    files = {rel: note}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} completed {sc.stage} for task {sc.task_id}.",
        diagnostics=[_diag(sc.stage, agent, f"{agent} summary for {sc.stage}", f"Prior memory: {sc.memory_hint()}. Context: {sc.context}")],
        artifacts=[_artifact(f"artifact-{sc.stage.lower()}", f"{sc.stage.lower()}_summary.md",
                             "REPORT", agent, rel)],
        workspace_files=files,
        recommended_next="Confirm orchestrator approval and continue the remaining DAG.",
        structured_conclusion={},
        artifact_refs=list(files.keys()),
    )


STAGE_HANDLERS = {
    "SPEC_INGEST": run_spec_ingest,
    "PLAN": run_plan,
    "GOLDEN_GEN": run_golden_gen,
    "RTL_GEN": run_rtl_gen,
    "RTL_REPAIR": run_rtl_repair,
    "TB_GEN": run_tb_gen,
    "SIGNOFF": run_signoff,
    "EXPORT": run_export,
}


def dispatch(sc: StageContext) -> AgentResult:
    handler = STAGE_HANDLERS.get(sc.stage.upper(), run_fallback)
    return handler(sc)
