"""Stage-specialized agent handlers.

Replaces the single templated ``execute_agent`` path with explicit per-stage
strategies. Each handler receives a :class:`StageContext` (task info + resolved
workspace + prior memory + artifact inventory) and returns an
:class:`AgentResult`. Handlers write real files into the task workspace and also
return them in ``workspace_files`` so the orchestrator can index them.

The generation is deterministic (``LLM_PROVIDER=mock`` by default); the seams
for a real provider are the ``run_*`` functions.
"""
from __future__ import annotations

import json
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


def _slug(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return cleaned or "design"


def _diag(stage: str, agent: str, title: str, detail: str) -> Dict[str, Any]:
    return {
        "id": f"diag-{stage.lower()}",
        "title": title,
        "detail": detail,
        "confidence": "High · deterministic stage handler",
        "suggestedBy": agent,
    }


def run_spec_ingest(sc: StageContext) -> AgentResult:
    agent = "SpecInterpreter"
    brief = sc.design_brief
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
    }
    brief_md = (
        f"# Design Brief — {sc.task_name}\n\n{brief}\n\n"
        f"## Interfaces\n" + "\n".join(f"- `{p}`" for p in spec["interfaces"]) + "\n\n"
        f"## Assumptions\n" + "\n".join(f"- {a}" for a in spec["assumptions"]) + "\n\n"
        f"## Risks\n" + "\n".join(f"- {r}" for r in spec["risks"]) + "\n"
    )
    files = {
        "spec/design_brief.md": brief_md,
        "spec/spec.json": json.dumps(spec, indent=2),
    }
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} decomposed the design brief for {sc.task_name} into a structured spec.",
        diagnostics=[_diag(sc.stage, agent, "Spec decomposition", "Extracted interfaces, constraints, assumptions and risks.")],
        artifacts=[{"id": "artifact-spec", "name": "spec.json", "type": "SPEC", "owner": agent}],
        workspace_files=files,
        recommended_next="Review the structured plan and advance to PLAN.",
        structured_conclusion=spec,
        artifact_refs=list(files.keys()),
    )


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
    plan_md = (
        f"# Execution Plan — {sc.task_name}\n\n"
        f"Top module: `{sc.top_module}`\n\n## Checklist\n"
        + "\n".join(f"- [ ] {c}" for c in checklist)
        + "\n"
    )
    files = {"plans/execution_plan.md": plan_md}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} produced an execution plan and implementation checklist for {sc.task_name}.",
        diagnostics=[_diag(sc.stage, agent, "Execution plan", "Generated a staged implementation checklist.")],
        artifacts=[{"id": "artifact-plan", "name": "execution_plan.md", "type": "PLAN", "owner": agent}],
        workspace_files=files,
        recommended_next="Advance to RTL_GEN and generate the design sources.",
        structured_conclusion={"checklist": checklist},
        artifact_refs=list(files.keys()),
    )


def run_rtl_gen(sc: StageContext) -> AgentResult:
    agent = "RTLAuthor"
    top = sc.top_module
    result = rtl_author.generate_rtl(sc.design_brief, top)
    top = result.top
    status = "compiled cleanly" if result.compiled else "did NOT compile after repair"
    arch = (
        f"# RTL Architecture — {top}\n\n"
        f"Generated for task {sc.task_name} via `{result.provider}`.\n\n"
        f"- **Compile check (iverilog -tnull):** {status}\n"
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
    tone = "success" if result.compiled else "warning"
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated RTL for {sc.task_name} ({result.provider}, {status}).",
        diagnostics=[_diag(sc.stage, agent, "RTL generation summary",
                           f"Authored rtl/{top}.sv via {result.provider}; compiled={result.compiled}; attempts={result.attempts}.")],
        artifacts=[{"id": "artifact-rtl-top", "name": f"{top}.sv", "type": "RTL", "owner": agent}],
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


def run_rtl_repair(sc: StageContext) -> AgentResult:
    """Conditional stage: re-run the compile-repair loop on existing RTL.

    Reads the current top-module RTL from the workspace, compile-checks it and,
    if it fails, asks the model to repair it (feeding compiler errors + seed
    fix hints). No-ops cleanly when the RTL already compiles.
    """
    agent = "RTLAuthor"
    top = sc.top_module
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
        runtime = rtl_author.build_llm_runtime()
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
        artifacts=[{"id": "artifact-rtl-repair", "name": "rtl_repair.md", "type": "REPORT", "owner": agent}],
        workspace_files=files,
        recommended_next="Re-run SIM/LINT on the repaired RTL." if repaired else "RTL already clean; continue the DAG.",
        structured_conclusion={"top_module": top, "compiled": ok, "rounds": attempts, "repaired": repaired},
        artifact_refs=list(files.keys()),
    )


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
    tb = rtl_author.generate_tb(rtl_code, top, sc.design_brief)
    files = {f"tb/{top}_tb.sv": tb if tb.endswith("\n") else tb + "\n"}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} generated a self-checking testbench for {top}.",
        diagnostics=[_diag(sc.stage, agent, "Testbench generation", f"Authored tb/{top}_tb.sv with waveform dump and self-check.")],
        artifacts=[{"id": "artifact-tb", "name": f"{top}_tb.sv", "type": "TESTBENCH", "owner": agent}],
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
        artifacts=[{"id": "artifact-signoff", "name": "signoff_summary.md", "type": "REPORT", "owner": agent}],
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
    sc.persist(files)
    pdf_rel = None
    if sc.workspace is not None:
        pdf_rel = generate_pdf(sc.workspace, ctx)
    artifact_refs = list(files.keys())
    artifacts = [
        {"id": "artifact-final-report", "name": "final_design_report.md", "type": "REPORT", "owner": agent},
        {"id": "artifact-runbook", "name": "runbook.md", "type": "RUNBOOK", "owner": agent},
        {"id": "artifact-architecture", "name": "architecture_overview.md", "type": "ARCHITECTURE", "owner": agent},
    ]
    if pdf_rel:
        artifact_refs.append(pdf_rel)
        artifacts.append({"id": "artifact-pdf", "name": "final_report.pdf", "type": "REPORT", "owner": agent})
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
    files = {f"reports/{sc.stage.lower()}_notes.md": note}
    sc.persist(files)
    return AgentResult(
        agent_name=agent,
        summary=f"{agent} completed {sc.stage} for task {sc.task_id}.",
        diagnostics=[_diag(sc.stage, agent, f"{agent} summary for {sc.stage}", f"Prior memory: {sc.memory_hint()}. Context: {sc.context}")],
        artifacts=[{"id": f"artifact-{sc.stage.lower()}", "name": f"{sc.stage.lower()}_summary.md", "type": "REPORT", "owner": agent}],
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
