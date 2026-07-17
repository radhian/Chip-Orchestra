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
    """Run one stage's deep agent (file + web + memory + python tools)."""
    from research import make_step_tools
    from .deep_agent import run_step_agent
    _apply_model(sc)
    return run_step_agent(
        sc.workspace, goal,
        extra_tools=make_step_tools(sc.workspace),
        on_clean_write=on_clean_write,
        recursion_limit=recursion_limit,
        log_name=log_name,
    )


_TEXT_EXT = {".v", ".sv", ".vh", ".svh", ".md", ".json", ".txt", ".mem", ".log", ".xdc", ".sdc"}


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
    """The rtl/ files the PLAN stage's build contract (context/design_notes.md)
    commits to — the generation completeness gate holds RTL_GEN to this list,
    which is what forces a MULTI-FILE decomposition instead of one big .v."""
    if sc.workspace is None:
        return []
    dn = sc.workspace / "context" / "design_notes.md"
    if not dn.is_file():
        return []
    text = dn.read_text(errors="replace")
    files: List[str] = []
    for m in re.finditer(r"\brtl/([\w\-]+\.(?:sv|v|vh|svh|mem))\b", text):
        name = m.group(1)
        if name not in files:
            files.append(name)
    return files[:24]


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
        recommended_next="Advance to RTL_GEN and generate the design sources.",
        structured_conclusion={"checklist": checklist, "deep_agent": bool(deep_note),
                               "web_research": bool(research_summary)},
        artifact_refs=list(files.keys()),
    )


# --------------------------------------------------------------------------- #
# RTL_GEN — deep-agent generation with compile-on-write, rtl_author fallback
# --------------------------------------------------------------------------- #
def _rtl_status(workspace: Path) -> Dict[str, Any]:
    """Compile status of every RTL file on disk + the detected top module."""
    rtl_dir = workspace / "rtl"
    status: Dict[str, Any] = {"files": [], "broken": {}, "top": ""}
    if not rtl_dir.is_dir():
        return status
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
                "algorithm the design brief specifies and must COMPUTE AND OUTPUT the solved "
                "result for the canonical input (context/chip_input_grid.json) — for a "
                "maze/navigation brief, the route from start to goal, observable at the "
                "chip's outputs. If the algorithm uses NN weights (e.g. DDPG actor/critic), "
                "TRAIN/DERIVE them in Python (run_python, numpy) so the policy ACTUALLY "
                "solves the canonical input, QUANTIZE with the RTL's fixed-point format, and "
                "bake them into rtl/*.mem — the weights are part of the chip. Do not "
                "substitute a different algorithm to make the task easier.\n")
        goal = (
            f"Design complete, synthesizable Verilog-2001 for this hardware: {sc.design_brief}\n"
            "PORT RULE: module ports must be plain Verilog-2001 packed vectors ONLY. NEVER "
            "use unpacked array ports (`output reg [7:0] q [0:3]`) — iverilog accepts them "
            "but the hardening flow's yosys Verilog-2005 frontend REJECTS them and PNR dies; "
            "flatten to a packed vector (`output reg [4*8-1:0] q_flat`) instead. Unpacked "
            "arrays INSIDE modules (memories) are fine.\n"
            + _digest_note(sc)
            + func_note
            + notes
            + _anchor_note(sc)
            + "DECOMPOSE the design into MULTIPLE files — ONE module per file "
              "(`rtl/<module>.v` or `.sv`), a shared header (`rtl/params.vh`) for common "
              "`define/parameters, plus `rtl/<name>.mem` data files where needed — and a TOP "
              "module that instantiates and wires the submodules. A real chip is never one "
              "monolithic file. Write each file with write_file_disk. EVERY write of a .v/.sv "
              "file returns a COMPILE CHECK result — if it reports errors, FIX that file and "
              "write it again immediately; never leave a file broken.\n"
              "Reference shared macros WITH the backtick (`WIDTH) and `include \"params.vh\" in "
              "every file that uses them.\n"
              "ONLY IF the design is genuinely DATA-DRIVEN (a function LUT, filter taps, or NN "
              "weights) COMPUTE the values with run_python (numpy) — pip_install what you need — "
              "QUANTIZE, write them to rtl/<name>.mem and load with $readmemh/$readmemb. The "
              "Python is a throw-away generator; do NOT add a .py file to the design. For "
              "ordinary arithmetic, use NO Python at all.\n"
              "When every file exists and compiles clean, reply just 'done' — your RTL is the "
              "files on disk; do NOT paste the whole design back.\n"
            + PITFALLS
        )
        _run_deep(sc, goal, "rtl_gen_deep_agent", recursion_limit=80)

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
        for _pass in range(3):
            if status["files"] and not status["broken"] and not miss:
                break
            broken_note = "".join(
                f"- FIX rtl/{f} — its compile errors:\n{e[:500]}\n"
                for f, e in status["broken"].items())
            goal2 = (
                f"You are STILL generating RTL for: {sc.design_brief}. "
                f"Already written: {', '.join(status['files']) or '(none)'}.\n"
                + _anchor_note(sc)
                + (("WRITE THE MISSING PLANNED FILES NOW — complete and synthesizable, ONE "
                    "write_file_disk call each, reusing the interfaces in "
                    "context/design_notes.md and the existing modules. Do NOT rewrite working "
                    "files:\n" + "\n".join(f"- rtl/{f}" for f in miss) + "\n") if miss else "")
                + (("These files FAILED their compile check — read each, fix the exact errors, "
                    "write it back; the write result must say 'compile check clean':\n" + broken_note)
                   if status["broken"] else "")
                + ("NO RTL exists yet — write the design's modules to rtl/ NOW, one "
                   "write_file_disk call each.\n" if not status["files"] else "")
                + "When every file exists AND compiles clean, reply 'done'.\n" + PITFALLS
            )
            _run_deep(sc, goal2, f"rtl_gen_deep_agent_fix{_pass + 1}", recursion_limit=60)
            status = _rtl_status(sc.workspace)
            miss = _missing(status)
        _log_state(sc, "generate:done",
                   f"files={status['files']}, broken={list(status['broken']) or 'none'}, "
                   f"planned-missing={miss or 'none'}")

        if status["files"]:
            top = status["top"] or top
            compiled = not status["broken"]
            files = _files_from_disk(sc.workspace, ["rtl"])
            arch = (
                f"# RTL Architecture — {top}\n\n"
                f"Generated for task {sc.task_name} by the RLM deep agent.\n\n"
                f"- **Top module:** `{top}`\n"
                f"- **Files:** " + ", ".join(f"`rtl/{f}`" for f in status["files"]) + "\n"
                f"- **Compile check:** " + ("all clean ✓" if compiled else
                                            f"{len(status['broken'])} file(s) still broken: "
                                            + ", ".join(status["broken"])) + "\n"
            )
            files["reports/rtl_architecture.md"] = arch
            sc.persist({"reports/rtl_architecture.md": arch})
            artifacts = [_artifact(f"artifact-rtl-{Path(f).stem}", f, "RTL", agent, f"rtl/{f}")
                         for f in status["files"]]
            artifacts.append(_artifact("artifact-rtl-arch", "rtl_architecture.md", "REPORT",
                                       agent, "reports/rtl_architecture.md"))
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} generated {len(status['files'])} RTL module file(s) for "
                        f"{sc.task_name} (deep agent, "
                        + ("compile clean" if compiled else "compile errors remain") + ").",
                diagnostics=[_diag(sc.stage, agent, "RTL generation summary",
                                   f"Deep agent wrote {status['files']}; top={top}; "
                                   f"broken={list(status['broken']) or 'none'}.",
                                   confidence="Deep agent")],
                artifacts=artifacts,
                workspace_files=files,
                recommended_next=("Validate generated RTL and queue verification stages."
                                  if compiled else "RTL failed compile-check; run RTL_REPAIR."),
                structured_conclusion={
                    "top_module": top,
                    "files": [f"rtl/{f}" for f in status["files"]],
                    "compiled": compiled,
                    "provider": "deep-agent",
                },
                artifact_refs=list(files.keys()),
            )
        # deep agent produced nothing usable → fall through to the one-shot path

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
        f"rtl/{top}.sv": result.code if result.code.endswith("\n") else result.code + "\n",
        "reports/rtl_architecture.md": arch,
    }
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated RTL for {sc.task_name} ({result.provider}, {status_label}).",
        diagnostics=[_diag(sc.stage, agent, "RTL generation summary",
                           f"Authored rtl/{top}.sv via {result.provider}; compiled={result.compiled}; attempts={result.attempts}.")],
        artifacts=[_artifact("artifact-rtl-top", f"{top}.sv", "RTL", agent, f"rtl/{top}.sv"),
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
                + canonical_note +
                "\nDebug the CHIP'S BEHAVIOUR from the design's own evidence:\n"
                "1. Read the failing vectors in the log — which expected vs. actual mismatched;\n"
                "2. run_python a golden model of the function to COMPUTE the correct values;\n"
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
    agent = "Verifier"
    top = sc.top_module
    rtl_code = ""
    if sc.workspace is not None:
        candidate = sc.workspace / "rtl" / f"{top}.sv"
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
        tb_rel = f"tb/{top}_tb.sv"
        submodules = [Path(f).stem for f in status["files"]
                      if Path(f).stem != top and not f.endswith((".vh", ".svh", ".mem"))][:6]
        unit_note = ""
        if submodules:
            unit_note = (
                "\nALSO write a small UNIT testbench per submodule (GarudaChip per-IP verify) — "
                "each `tb/<module>_tb.v` instantiates JUST that module, drives a few directed "
                "vectors with KNOWN expected outputs (compute them by hand or with a run_python "
                "golden model — never guess), CHECKS every one ($fatal on mismatch, per-vector "
                "$display of expected vs. actual), and $finish-es: "
                + ", ".join(f"tb/{m}_tb.v" for m in submodules) + ". An IP that is not checked "
                "against known-correct values is NOT verified.\n")
        # INFERENCE CONTRACT (GarudaChip): the stimulus is GENERATED in Python
        # and the RTL's computed RESULT is dumped by the tb — but ONLY images
        # classified as CHIP-INPUT DATA are fed to the chip; an architecture
        # diagram must never be turned into pixels.
        infer_note = ""
        try:
            from uploads import uploads_manifest
            manifest = uploads_manifest(sc.workspace)
        except Exception:  # noqa: BLE001
            manifest = {}
        data_images = [n for n, role in manifest.items() if role == "data"]
        if data_images:
            canonical = (sc.workspace / "context" / "chip_input_grid.json").is_file()
            infer_note = (
                "\nCHIP INPUT/OUTPUT: the attached image(s) "
                + ", ".join(f"`context/uploads/{n}`" for n in data_images)
                + " are CHIP INPUT DATA (classified by the vision triage). "
                + ("A CANONICAL input already exists from a previous run — "
                   "`context/chip_input_grid.json` (+ rtl/*_input.mem). REUSE IT EXACTLY; "
                   "do NOT re-derive the input from the image (re-deriving produced a "
                   "DIFFERENT input every run). "
                   if canonical else
                   "DERIVE the input DETERMINISTICALLY with run_python: SAMPLE the image "
                   "programmatically (PIL + numpy — locate the grid, read each cell's center "
                   "pixel, classify by color thresholds). Use `context/uploads_digest.md` only "
                   "for the grid SIZE and cell semantics — NEVER eyeball or invent cell values "
                   "(vision re-reading produced a different grid every run). Save the parsed "
                   "grid to `context/chip_input_grid.json` so every later run reuses the SAME "
                   "input. ")
                + "Write the stimulus as `rtl/<name>.mem` for $readmemh, save a faithful "
                "visualization to `waves/chip_input.png` (it must match the uploaded image's "
                "layout), and write the side length to `context/input_size.txt`.\n"
                "PYTHON FIRST, THEN RTL — the verification order is:\n"
                "1. Write the GOLDEN MODEL in run_python, feed it the canonical input, and "
                "verify ITS output makes sense (print the input grid AND the computed "
                "desired output grid side by side). Save the desired output to "
                "`waves/golden_output.mem` — SAME format as the input mem (N*N hex values, "
                "row-major, same legend, PLUS the computed RESULT marked with distinct "
                "values: for a pathfinding/navigation design the SOLVED PATH cells from "
                "start to goal MUST be marked with value 4, so the rendered image "
                "(0=white,1=black,2=red start,3=green goal,4=blue path) actually SHOWS the "
                "route). It is rendered to waves/golden_output.png automatically.\n"
                "2. Make the MAIN testbench DUMP the chip's computed RESULT with $writememh "
                "into `waves/chip_output.mem` — EXACTLY the same format/order as "
                "golden_output.mem. Grid cells hold values 0..4, so every grid register "
                "must be AT LEAST 3 bits wide (`reg [2:0]` — a `reg [1:0]` silently "
                "truncates the path value 4 to 0 and fakes a pass). The OUTPUT must come "
                "from the DUT's ports/memory — never copied from the golden model.\n"
                "3. The SIM stage COMPARES chip_output.mem against golden_output.mem value "
                "by value and FAILS on any mismatch — the chip is only correct when "
                "input → RTL output equals input → Python output.\n"
                "Architecture/reference images are NOT chip input — do not feed them to "
                "the DUT.\n")
        elif any(f.endswith(".mem") for f in status["files"]):
            infer_note = (
                "\nCHIP INPUT/OUTPUT: the design loads .mem data. Make the MAIN testbench "
                "DUMP the chip's computed RESULT with $writememh into "
                "`waves/chip_output.mem` and $display the key output values — the OUTPUT "
                "must come from the DUT's ports, never from the golden model.\n")
        goal = (
            f"Write SELF-CHECKING testbenches for this design (top module `{top}`; design "
            f"intent: {sc.design_brief}).\n"
            "First read_file_disk the top module (and grep_files its submodule interfaces as "
            "needed) so every port list is EXACT. Write the MAIN testbench to "
            f"`{tb_rel}`: instantiate `{top}` as `dut`, drive a clock and reset, apply "
            "meaningful stimulus, CHECK outputs against expected values ($fatal/$error on "
            "mismatch, $display \"TEST PASSED\" on success), dump waves with "
            "$dumpfile(\"design.vcd\") + $dumpvars, and end with $finish.\n"
            + infer_note
            + unit_note
            + "VERIFIABILITY IS THE CONTRACT: every checked value must be compared against an "
              "INDEPENDENTLY computed expectation. Write a run_python golden model of the "
              "chip's function, feed it the SAME stimulus, and bake its outputs into the "
              "testbench's expected values (or a .mem the tb compares against). A testbench "
              "that only toggles inputs or checks 'output changed' proves nothing. On "
              "mismatch, $display the failing vector (inputs, expected, actual) so the "
              "repair stage can act on it.\n"
              "Each write result compiles the tb WITH its DUT — if it reports errors, fix and "
              "rewrite until clean. When the main testbench (and unit tbs) compile clean, "
              "reply 'done'."
        )
        _run_deep(sc, goal, "tb_gen_deep_agent", recursion_limit=70)
        # DETERMINISTIC deliverable check — the tb must dump waves ($dumpfile)
        # and, for data designs, the chip's output mem ($writememh). Asking is
        # not enough: a missing dump previously slipped through and the SIM
        # verifiable-output gate failed the whole stage later.
        tb_path = sc.workspace / tb_rel
        needs_output = bool(data_images) or any(f.endswith(".mem") for f in status["files"])
        for _fix in range(2):
            if not tb_path.is_file():
                break
            tb_text = tb_path.read_text(errors="replace")
            missing = []
            if "$dumpfile" not in tb_text:
                missing.append('waveform dump: $dumpfile("design.vcd"); $dumpvars(0, ' + f"{top}_tb);")
            if needs_output and "$writememh" not in tb_text:
                missing.append('chip-output dump: $writememh("waves/chip_output.mem", <result array>);')
            if re.search(r"\$writememh\s*\(\s*\"[^\"]*golden", tb_text):
                missing.append('REMOVE the testbench\'s $writememh of waves/golden_output.mem — the '
                               'desired output must be produced by the Python golden model '
                               '(run_python), never fabricated by the testbench')
            golden_path = sc.workspace / "waves" / "golden_output.mem"
            if needs_output and not golden_path.is_file():
                missing.append('golden desired output: run_python the golden model on the canonical '
                               'input and write waves/golden_output.mem (same N*N row-major hex '
                               'format as the input mem) — SIM compares the chip output against it')
            elif needs_output and (sc.workspace / "context" / "chip_input_grid.json").is_file():
                # The FUNCTIONAL REQUIREMENT is non-negotiable: the desired
                # output must contain the SOLVED route (cells marked 4). A
                # repair round once redefined the golden as "agent wanders,
                # no path" and the comparison passed trivially.
                tokens = set(re.sub(r"//[^\n]*", " ", golden_path.read_text(errors="replace")).split())
                if not ({"4", "04"} & tokens):
                    missing.append(
                        "the golden output has NO route cells — the desired output must show the "
                        "algorithm SOLVING the task. Implement the ALGORITHM THE DESIGN BRIEF "
                        f"SPECIFIES ('{sc.design_brief[:160]}') in Python with the SAME fixed-point "
                        "arithmetic and the SAME rtl/*.mem weights as the RTL. If the current "
                        "weights do not reach the goal, TRAIN/DERIVE weights in Python that DO "
                        "(GarudaChip data-driven design: the NN weights are baked into the chip — "
                        "compute good ones), update the rtl/*.mem weight files, and write the "
                        "policy's goal-reaching trajectory (cells marked 4) to "
                        "waves/golden_output.mem. Do NOT redefine the desired output as 'agent "
                        "did not reach the goal', and do NOT swap the algorithm for a planner "
                        "the brief did not ask for")
            if not missing:
                break
            _run_deep(sc,
                      f"The testbench `{tb_rel}` is missing REQUIRED deliverables:\n- "
                      + "\n- ".join(missing)
                      + "\nread_file_disk it, ADD the missing statements (before $finish; the "
                        "output dump must write the DUT's COMPUTED result array), and write it "
                        "back compile-clean. Change nothing else. Reply 'done'.",
                      f"tb_gen_deep_agent_deliverables{_fix + 1}", recursion_limit=30)
        if tb_path.is_file():
            clean = True
            try:
                from verilog_check import check_tb
                clean = not check_tb(tb_path, sc.workspace / "rtl")
            except Exception:  # noqa: BLE001
                pass
            files = _files_from_disk(sc.workspace, ["tb"])
            tb_names = sorted(Path(p).name for p in files if p.endswith((".v", ".sv")))
            _log_state(sc, "testbench:done", f"testbenches={tb_names}, top tb clean={clean}")
            artifacts = [_artifact(f"artifact-tb-{Path(p).stem}", Path(p).name, "TESTBENCH",
                                   agent, p)
                         for p in sorted(files) if p.endswith((".v", ".sv"))]
            return AgentResult(
                agent_name=agent,
                summary=f"{agent} generated {len(artifacts)} self-checking testbench(es) for "
                        f"{top} (deep agent, "
                        + ("compile clean" if clean else "compile errors remain") + ").",
                diagnostics=[_diag(sc.stage, agent, "Testbench generation",
                                   f"Authored {', '.join(tb_names)} with waveform dump and "
                                   f"self-check; top tb clean={clean}.", confidence="Deep agent")],
                artifacts=artifacts,
                workspace_files=files,
                recommended_next="Review verification notes and move into the next scheduled EDA stage.",
                structured_conclusion={"testbench": tb_rel, "testbenches": tb_names,
                                       "compiled": clean},
                artifact_refs=list(files.keys()),
            )
        # deep agent didn't produce the tb → fall through

    tb = rtl_author.generate_tb(rtl_code, top, sc.design_brief,
                                runtime=rtl_author.build_llm_runtime(sc.llm_model))
    files = {f"tb/{top}_tb.sv": tb if tb.endswith("\n") else tb + "\n"}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated a self-checking testbench for {top}.",
        diagnostics=[_diag(sc.stage, agent, "Testbench generation", f"Authored tb/{top}_tb.sv with waveform dump and self-check.")],
        artifacts=[_artifact("artifact-tb", f"{top}_tb.sv", "TESTBENCH", agent, f"tb/{top}_tb.sv")],
        workspace_files=files,
        recommended_next="Review verification notes and move into the next scheduled EDA stage.",
        structured_conclusion={"testbench": f"tb/{top}_tb.sv"},
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


def run_export(sc: StageContext) -> AgentResult:
    agent = "FlowAssistant"
    if sc.workspace is not None:
        ctx = collect_evidence(sc.task_id, sc.workspace, sc.context, sc.eda_reports, sc.reference_files)
    else:
        from reporting.evidence import ReportContext

        ctx = ReportContext(task_id=sc.task_id, task_name=sc.task_name, design_brief=sc.design_brief, top_module=sc.top_module)
    files = generate_reports(ctx)
    # Full LaTeX design report (spec → GDS, with figures and the LibreLane
    # parameter table) — compile with `pdflatex exports/final_report.tex` from
    # the workspace root.
    try:
        from reporting.latex_report import generate_latex
        workspace_files = wsfiles.list_files(sc.workspace) if sc.workspace else []
        files["exports/final_report.tex"] = generate_latex(ctx, workspace_files)
    except Exception:  # noqa: BLE001 - LaTeX report is best-effort
        pass
    sc.persist(files)
    pdf_rel = None
    if sc.workspace is not None:
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
    if "exports/final_report.tex" in files:
        artifacts.append(_artifact("artifact-latex", "final_report.tex", "REPORT", agent,
                                   "exports/final_report.tex"))
    if pdf_rel:
        artifact_refs.append(pdf_rel)
        artifacts.append(_artifact("artifact-pdf", "final_report.pdf", "REPORT", agent, pdf_rel))
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} assembled the final report, runbook, architecture overview"
                + (" and PDF" if pdf_rel else "") + f" for {sc.task_name}.",
        diagnostics=[_diag(sc.stage, agent, "Report assembly",
                           "Generated evidence-backed markdown reports" + (" and a bundled PDF." if pdf_rel else "."))],
        artifacts=artifacts,
        workspace_files=files,
        recommended_next="Publish the final report and close out the task.",
        structured_conclusion={"reports": list(files.keys()), "pdf": pdf_rel, "tapeout_ready": ctx.tapeout_ready},
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
    "RTL_GEN": run_rtl_gen,
    "RTL_REPAIR": run_rtl_repair,
    "TB_GEN": run_tb_gen,
    "SIGNOFF": run_signoff,
    "EXPORT": run_export,
}


def dispatch(sc: StageContext) -> AgentResult:
    handler = STAGE_HANDLERS.get(sc.stage.upper(), run_fallback)
    return handler(sc)
