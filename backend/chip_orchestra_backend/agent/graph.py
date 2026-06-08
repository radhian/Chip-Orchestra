"""The agentic RTL-to-GDSII pipeline as a LangGraph state graph.

Mirrors GarudaChip's node set (plan -> generate -> decompose -> testbench ->
simulate -> self-correct -> harden) but every node reports progress through a
``Reporter`` that maps it onto the Chip Orchestra task model (stages, runbook
events, artifacts, diagnoses, workspace files, signoff) instead of a Streamlit
transcript.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .. import control
from ..config import get_settings
from ..models import DiagnosisItem, SignoffChecklistItem, SignoffStatus
from ..store import TaskStore
from . import eda, prompts
from .llm import (
    complete,
    extract_code_block,
    guess_tb_module,
    guess_top_module,
    split_verilog_modules,
    strip_reasoning,
)


class GraphState(TypedDict, total=False):
    task_id: str
    brief: str
    model: str | None
    clock_period_ns: float
    pdk: str
    stdcell: str
    run_harden: bool
    max_retries: int
    research_depth: str

    plan: str
    reference: str
    generation: str
    decomposed: dict[str, str]
    top_module: str
    testbench: dict[str, str]
    sim_output: str
    sim_ok: bool
    error_count: int
    route: str
    harden_ok: bool
    harden_tool_missing: bool
    harden_output: str
    gds_path: str | None
    metrics: dict


# Chip Orchestra's five canonical stages (must match the frontend stage keys).
STAGE_SPEC = "spec-intake"
STAGE_PLAN = "agent-planning"
STAGE_VERIFY = "verification-loop"
STAGE_IMPL = "implementation"
STAGE_DELIVER = "delivery"


class Reporter:
    """Binds the agent nodes to one task in the store."""

    def __init__(self, store: TaskStore, task_id: str) -> None:
        self.store = store
        self.task_id = task_id

    def event(self, title: str, detail: str, tone: str = "info") -> None:
        self.store.add_event(self.task_id, title, detail, tone)

    def stage(self, key: str, status: str, **flags) -> None:
        self.store.set_stage(self.task_id, key, status, **flags)

    def status(self, **kwargs) -> None:
        self.store.set_status(self.task_id, **kwargs)

    def artifact(self, name: str, type_: str, owner: str) -> None:
        self.store.add_artifact(self.task_id, name, type_, owner)

    def file(self, rel_path: str, content: str, *, note: str, status: str) -> None:
        self.store.register_workspace_file(self.task_id, rel_path, content, note=note, status=status)

    def clear(self, subdir: str) -> None:
        self.store.clear_workspace_subdir(self.task_id, subdir)

    def diagnoses(self, items: list[DiagnosisItem]) -> None:
        self.store.set_diagnoses(self.task_id, items)

    def signoff(self, signoff: SignoffStatus) -> None:
        self.store.set_signoff(self.task_id, signoff)

    @property
    def workspace(self) -> Path:
        return self.store.workspace_dir(self.task_id)


def _snippet(text: str, limit: int = 220) -> str:
    text = " ".join(strip_reasoning(text).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def build_pipeline(reporter: Reporter):
    """Compile a LangGraph pipeline whose nodes report into ``reporter``."""
    settings = get_settings()

    # --- nodes -------------------------------------------------------------
    def node_plan(state: GraphState) -> GraphState:
        reporter.status(status_label="Running", tone="running", current_stage="Spec intake",
                        eta_label="Planning", attempt_status="running")
        reporter.stage(STAGE_SPEC, "active")
        reporter.event("Spec ingested", f"Design brief accepted: {_snippet(state['brief'], 140)}", "info")
        plan = strip_reasoning(complete(prompts.PLAN_PROMPT.format(brief=state["brief"]), model=state.get("model"), task_id=state["task_id"]))
        reporter.event("Planner generated build plan", _snippet(plan), "info")
        reporter.file("docs/plan.md", plan, note="Agent build plan", status="Plan")
        reporter.artifact("plan.md", "Plan", "Planner agent")
        reporter.stage(STAGE_SPEC, "done")
        reporter.stage(STAGE_PLAN, "active")
        reporter.status(current_stage="Agent planning")
        return {"plan": plan}

    def node_retrieve(state: GraphState) -> GraphState:
        if not (settings.use_web or settings.use_rag):
            return {}
        from . import research

        depth = (state.get("research_depth") or "MEDIUM").upper()
        preset = research.RESEARCH_DEPTH.get(depth, research.RESEARCH_DEPTH["MEDIUM"])
        reporter.event(
            "Researching references",
            f"{depth.title()} research: up to {preset['github']} GitHub + {preset['web']} web sources, "
            "crawled and RAG-ranked into the generator.",
            "info",
        )
        try:
            reference, sources = research.gather_reference(state["brief"], depth, task_id=state["task_id"])
        except Exception as exc:  # noqa: BLE001 - research is best-effort
            reporter.event("Research skipped", f"Reference retrieval unavailable: {type(exc).__name__}: {exc}", "warning")
            return {}

        if reference:
            source_list = "\n".join(f"- {url}" for url in sources) or "- (no public sources)"
            reporter.file(
                "docs/references.md",
                f"# Retrieved reference context (RAG)\n\nSources:\n{source_list}\n\n---\n\n{reference}",
                note="RAG reference context",
                status="Reference",
            )
            reporter.artifact("references.md", "Reference", "Research agent")
            reporter.event(
                "References retrieved",
                f"Indexed {len(sources)} source(s); injecting the top {settings.rag_top_k} matches into the generator.",
                "success",
            )
            return {"reference": reference}

        reporter.event("No references found", "Proceeding with the model's own knowledge.", "info")
        return {}

    def node_generate(state: GraphState) -> GraphState:
        ref_note = " (grounded in retrieved references)" if state.get("reference") else ""
        reporter.event("Verilog generator started", f"Drafting synthesizable RTL from the brief and plan{ref_note}.", "info")
        reference = state.get("reference", "")
        ref_block = f"\nReference design for inspiration:\n```verilog\n{reference}\n```\n" if reference else ""
        prompt = prompts.GENERATE_PROMPT.format(
            brief=state["brief"], plan=state.get("plan", ""),
            reference=ref_block, pitfalls=prompts.PITFALLS,
        )
        rtl = extract_code_block(complete(prompt, model=state.get("model"), task_id=state["task_id"]), "verilog")
        if not rtl.strip():
            # The (thinking) response left no code — retry once with reasoning off.
            reporter.event("Empty RTL — retrying", "First pass returned no code; retrying with reasoning disabled.", "warning")
            rtl = extract_code_block(
                complete(prompt + "\n/no_think", model=state.get("model"), temperature=0.3, task_id=state["task_id"]),
                "verilog",
            )

        top = guess_top_module(rtl, fallback="dut")
        reporter.event("RTL generated", f"Top module `{top}` drafted ({rtl.count(chr(10)) + 1} lines).", "success")
        reporter.status(current_stage="RTL drafting")
        return {"generation": rtl, "top_module": top}

    def _write_rtl_files(rtl: str, top: str, *, status: str, note: str) -> dict[str, str]:
        """Split combined RTL into one file per module and (re)write rtl/ cleanly."""
        files = split_verilog_modules(rtl) or {f"{top}.v": rtl}
        reporter.clear("rtl")  # drop stale module files so there are no duplicates
        for name, content in files.items():
            reporter.file(f"rtl/{name}", content, note=f"{note} ({name})", status=status)
        return files

    def node_decompose(state: GraphState) -> GraphState:
        files = _write_rtl_files(state["generation"], state["top_module"], status="RTL draft", note="RTL module")
        reporter.artifact(next(iter(files)), "RTL", "Verilog generator")
        plural = "module file" if len(files) == 1 else "module files"
        reporter.event("RTL split into modules", f"{len(files)} {plural}: {', '.join(files)}.", "info")
        reporter.stage(STAGE_PLAN, "done")
        reporter.stage(STAGE_VERIFY, "active")
        reporter.status(current_stage="Verification loop", eta_label="Simulating")
        return {"decomposed": files}

    def node_testbench(state: GraphState) -> GraphState:
        top = state["top_module"]
        raw = complete(
            prompts.TESTBENCH_PROMPT.format(top=top, rtl=state["generation"]),
            model=state.get("model"),
        )
        tb = extract_code_block(raw, "verilog")
        tb_name = f"{top}_tb.v"
        reporter.file(f"tb/{tb_name}", tb, note="Self-checking testbench", status="Healthy")
        reporter.artifact(tb_name, "Testbench", "Testbench writer")
        reporter.event("Testbench generated", f"Self-checking TB `{tb_name}` ready for simulation.", "info")
        return {"testbench": {tb_name: tb}}

    def node_simulate(state: GraphState) -> GraphState:
        top = state["top_module"]
        ws = reporter.workspace
        sources = sorted((ws / "rtl").glob("*.v")) + sorted((ws / "rtl").glob("*.vh"))
        tb_files = sorted((ws / "tb").glob("*.v"))
        sources += tb_files
        # Detect the testbench top module (the model may not name it exactly `tb`).
        tb_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tb_files)
        tb_top = guess_tb_module(tb_text, fallback="tb")
        reporter.event("Icarus simulation launched", "Compiling RTL + testbench with iverilog and running vvp.", "info")
        result = eda.simulate(ws / "sim", sources, top_module=tb_top)
        reporter.file("sim/simulation.log", result.output or "(no output)", note="Simulation log", status="Log")
        reporter.artifact("simulation.log", "Report", "Verification loop")

        if result.tool_missing:
            reporter.event("Simulator unavailable", "iverilog/vvp not found on PATH; skipping verification.", "warning")
            return {"sim_ok": False, "sim_output": result.output, "error_count": state.get("max_retries", 3) + 1}

        if result.ok:
            reporter.event("Simulation passed", "Self-checking testbench reported Result: PASSED.", "success")
            if result.vcd_path:
                reporter.artifact(Path(result.vcd_path).name, "Waveform", "Verification loop")
            return {"sim_ok": True, "sim_output": result.output}

        count = state.get("error_count", 0) + 1
        reporter.event("Simulation failed", _snippet(result.output, 260), "warning")
        return {"sim_ok": False, "sim_output": result.output, "error_count": count}

    def node_route_fix(state: GraphState) -> GraphState:
        raw = complete(
            prompts.ROUTE_PROMPT.format(brief=state["brief"], sim_output=_snippet(state["sim_output"], 600)),
            model=state.get("model"),
        )
        decision = "design" if "DESIGN" in strip_reasoning(raw).upper() else "testbench"
        target = "RTL design" if decision == "design" else "testbench"
        reporter.event(
            f"Root cause clustered: {target}",
            f"Attempt {state.get('error_count', 1)} — agent will repair the {target} and re-simulate.",
            "warning",
        )
        reporter.diagnoses([
            DiagnosisItem(
                id="diag-active",
                title=f"Auto-repair targeting the {target}",
                detail=_snippet(state["sim_output"], 240),
                confidence=f"Attempt {state.get('error_count', 1)} of {state.get('max_retries', 3)}",
                primaryFile=f"rtl/{state['top_module']}.v" if decision == "design"
                else f"tb/{state['top_module']}_tb.v",
                suggestedBy="Verification loop agent",
            )
        ])
        return {"route": decision}

    def node_fix_design(state: GraphState) -> GraphState:
        temp = min(0.2 + 0.2 * state.get("error_count", 1), 0.85)
        raw = complete(
            prompts.FIX_DESIGN_PROMPT.format(
                sim_output=_snippet(state["sim_output"], 800),
                rtl=state["generation"], pitfalls=prompts.PITFALLS,
            ),
            model=state.get("model"), temperature=temp, task_id=state["task_id"],
        )
        rtl = extract_code_block(raw, "verilog")
        top = guess_top_module(rtl, fallback=state["top_module"])
        files = _write_rtl_files(rtl, top, status="RTL patch", note="RTL patch (auto-repair)")
        reporter.artifact(next(iter(files)), "RTL", "Design corrector")
        reporter.event("RTL patch proposed", f"Regenerated {len(files)} module file(s) at temperature {temp:.2f}.", "info")
        return {"generation": rtl, "top_module": top, "decomposed": files}

    def node_fix_testbench(state: GraphState) -> GraphState:
        top = state["top_module"]
        raw = complete(
            prompts.FIX_TB_PROMPT.format(
                top=top, sim_output=_snippet(state["sim_output"], 800), rtl=state["generation"]
            ),
            model=state.get("model"),
        )
        tb = extract_code_block(raw, "verilog")
        tb_name = f"{top}_tb.v"
        reporter.file(f"tb/{tb_name}", tb, note="Testbench patch (auto-repair)", status="TB patch")
        reporter.event("Testbench rewritten", f"Regenerated self-checking TB `{tb_name}`.", "info")
        return {"testbench": {tb_name: tb}}

    def node_harden(state: GraphState) -> GraphState:
        reporter.stage(STAGE_VERIFY, "done")
        if not state.get("run_harden", True):
            reporter.event("Hardening skipped", "Launch mode requested generation/verification only.", "info")
            return {"harden_ok": False, "harden_output": "skipped", "harden_tool_missing": False}

        reporter.stage(STAGE_IMPL, "active")
        reporter.status(status_label="Running", tone="running", current_stage="Synthesis", eta_label="Hardening")
        reporter.event("LibreLane hardening launched", "Running RTL→GDSII (synthesis, P&R, signoff) via LibreLane.", "info")

        ws = reporter.workspace
        rtl_files = sorted((ws / "rtl").glob("*.v"))
        result = eda.harden(
            ws, design_name=state["top_module"], top_module=state["top_module"], rtl_files=rtl_files,
            clock_period_ns=state.get("clock_period_ns") or 10.0,
            pdk=state.get("pdk"), stdcell=state.get("stdcell"),
        )
        reporter.file("harden/librelane.log", result.output or "(no output)", note="LibreLane log", status="Log")

        if result.tool_missing:
            reporter.stage(STAGE_IMPL, "failed")
            reporter.event("LibreLane not available", "RTL verified but not hardened — configure LIBRELANE_CMD to enable GDSII.", "warning")
            reporter.diagnoses([
                DiagnosisItem(
                    id="diag-harden",
                    title="Enable LibreLane to complete RTL→GDSII",
                    detail="Verification passed. Install LibreLane (e.g. `nix run github:librelane/librelane`) "
                           "and set LIBRELANE_CMD in backend/.env to produce a GDSII and signoff metrics.",
                    confidence="Tooling — implementation stage blocked",
                    primaryFile=f"rtl/{state['top_module']}.v",
                    suggestedBy="Hardening agent",
                )
            ])
            return {"harden_ok": False, "harden_output": result.output, "harden_tool_missing": True}

        if result.ok:
            reporter.stage(STAGE_IMPL, "done")
            reporter.artifact(Path(result.gds_path).name if result.gds_path else f"{state['top_module']}.gds", "GDS", "Hardening agent")
            if result.metrics:
                reporter.file("harden/metrics.json", _as_json(result.metrics), note="Implementation metrics", status="Metric")
                reporter.artifact("metrics.json", "Metric", "Hardening agent")
            reporter.event("Hardening complete", "GDSII produced and implementation metrics normalized.", "success")
        else:
            reporter.stage(STAGE_IMPL, "failed")
            reporter.event("Hardening failed", _snippet(result.output, 260), "warning")
        return {
            "harden_ok": result.ok, "harden_output": result.output,
            "harden_tool_missing": False, "gds_path": result.gds_path, "metrics": result.metrics,
        }

    def node_finalize(state: GraphState) -> GraphState:
        sim_ok = state.get("sim_ok", False)
        harden_ok = state.get("harden_ok", False)
        harden_missing = state.get("harden_tool_missing", False)
        run_harden = state.get("run_harden", True)

        checklist = [
            SignoffChecklistItem(id="c-verify", label="Verification baseline frozen",
                                 detail="Self-checking simulation reported PASSED.", done=sim_ok),
            SignoffChecklistItem(id="c-impl", label="Implementation reports normalized",
                                 detail="LibreLane produced GDSII and metrics." if not harden_missing
                                 else "LibreLane not configured — install to harden.", done=harden_ok),
            SignoffChecklistItem(id="c-handoff", label="One-click handoff bundle",
                                 detail="Bundle ready once implementation completes.", done=harden_ok),
        ]
        package = ["Final RTL snapshot", "Self-checking testbench", "Simulation log"]
        if harden_ok:
            package += ["GDSII layout", "Implementation metrics", "LibreLane signoff reports"]

        if harden_ok:
            state_label, message = "Tapeout package candidate", "GDSII and reports are ready for the final review gate."
            reporter.stage(STAGE_DELIVER, "done")
            reporter.status(status_label="Passed", tone="passed", current_stage="Signoff package", eta_label="Ready",
                            attempt_status="succeeded")
            reporter.event("Signoff package assembled", "RTL, GDSII, reports, and approval trail bundled for handoff.", "success")
        elif sim_ok and (not run_harden or harden_missing):
            state_label = "Verified — awaiting implementation"
            message = ("RTL is verified. Implementation/GDSII pending LibreLane availability."
                       if harden_missing else "Generation/verification complete for this launch mode.")
            reporter.stage(STAGE_DELIVER, "queued")
            reporter.status(status_label="Needs review", tone="review", current_stage="Implementation review",
                            eta_label="Review", attempt_status="pending approval")
        else:
            state_label, message = "Blocked", "Verification did not converge — review the runbook and retry."
            reporter.stage(STAGE_DELIVER, "queued")
            reporter.status(status_label="Failed", tone="failed", current_stage="Verification loop",
                            eta_label="Retry", attempt_status="failed")

        reporter.signoff(SignoffStatus(
            stateLabel=state_label, message=message, packageContents=package, checklist=checklist,
        ))
        return {}

    def node_verify_failed(state: GraphState) -> GraphState:
        reporter.stage(STAGE_VERIFY, "failed")
        reporter.event("Verification did not converge",
                       f"Self-correction exhausted after {state.get('error_count', 0)} attempt(s).", "warning")
        return node_finalize({**state, "harden_ok": False})

    # --- routing -----------------------------------------------------------
    def after_sim(state: GraphState) -> str:
        if state.get("sim_ok"):
            return "harden"
        if state.get("error_count", 0) > state.get("max_retries", settings.max_retries):
            return "verify_failed"
        return "route_fix"

    def after_route(state: GraphState) -> str:
        return "fix_design" if state.get("route") == "design" else "fix_testbench"

    # Guard each node so a stop/cancel request pauses/aborts at the next boundary.
    def guarded(fn):
        def wrapper(state: GraphState) -> GraphState:
            control.checkpoint(state["task_id"])
            return fn(state)

        return wrapper

    # --- wiring ------------------------------------------------------------
    g = StateGraph(GraphState)
    g.add_node("plan", guarded(node_plan))
    g.add_node("retrieve", guarded(node_retrieve))
    g.add_node("generate", guarded(node_generate))
    g.add_node("decompose", guarded(node_decompose))
    g.add_node("testbench", guarded(node_testbench))
    g.add_node("simulate", guarded(node_simulate))
    g.add_node("route_fix", guarded(node_route_fix))
    g.add_node("fix_design", guarded(node_fix_design))
    g.add_node("fix_testbench", guarded(node_fix_testbench))
    g.add_node("harden", guarded(node_harden))
    g.add_node("finalize", guarded(node_finalize))
    g.add_node("verify_failed", guarded(node_verify_failed))

    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "decompose")
    g.add_edge("decompose", "testbench")
    g.add_edge("testbench", "simulate")
    g.add_conditional_edges("simulate", after_sim,
                            {"harden": "harden", "route_fix": "route_fix", "verify_failed": "verify_failed"})
    g.add_conditional_edges("route_fix", after_route,
                            {"fix_design": "fix_design", "fix_testbench": "fix_testbench"})
    g.add_edge("fix_design", "simulate")
    g.add_edge("fix_testbench", "simulate")
    g.add_edge("harden", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("verify_failed", END)
    # Checkpointer enables pause/resume: state is saved after each completed node.
    return g.compile(checkpointer=MemorySaver())


def _as_json(data: dict) -> str:
    import json

    return json.dumps(data, indent=2)
