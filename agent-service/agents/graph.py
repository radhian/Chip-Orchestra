from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph


@dataclass
class AgentResult:
    agent_name: str
    summary: str
    diagnostics: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    workspace_files: Dict[str, str]
    recommended_next: str


class DeepAgentGraph:
    def __init__(self, tool_registry, memory_store):
        self.tool_registry = tool_registry
        self.memory_store = memory_store
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(dict)
        workflow.add_node("load_memory", self.load_memory)
        workflow.add_node("select_agent", self.select_agent)
        workflow.add_node("execute_agent", self.execute_agent)
        workflow.add_node("persist_feedback", self.persist_feedback)
        workflow.set_entry_point("load_memory")
        workflow.add_edge("load_memory", "select_agent")
        workflow.add_edge("select_agent", "execute_agent")
        workflow.add_edge("execute_agent", "persist_feedback")
        workflow.add_edge("persist_feedback", END)
        return workflow.compile()

    def invoke(self, payload: Dict[str, Any]) -> AgentResult:
        state = self.graph.invoke(payload)
        return state["result"]

    def load_memory(self, state: Dict[str, Any]) -> Dict[str, Any]:
        stage = state.get("stage", "FLOW_ASSISTANT")
        task_id = state.get("task_id", "")
        memories = self.memory_store.search_memories(task_id=task_id, stage=stage)
        state["memories"] = memories
        return state

    def select_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        stage = state.get("stage", "FLOW_ASSISTANT")
        mapping = {
            "SPEC_INGEST": "SpecInterpreter",
            "PLAN": "FlowAssistant",
            "RTL_GEN": "RTLAuthor",
            "TB_GEN": "Verifier",
            "SIM": "Verifier",
            "LINT": "Diagnoser",
            "SYNTH": "Diagnoser",
            "PNR": "Diagnoser",
            "DRC_LVS": "Diagnoser",
            "SIGNOFF": "FlowAssistant",
            "EXPORT": "FlowAssistant",
            "FLOW_ASSISTANT": "FlowAssistant",
        }
        state["agent_name"] = mapping.get(stage, "FlowAssistant")
        return state

    def execute_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        agent_name = state["agent_name"]
        prompt = state.get("prompt", "")
        task_id = state.get("task_id", "")
        stage = state.get("stage", "FLOW_ASSISTANT")
        context = state.get("context", {})
        memories = state.get("memories", [])

        memory_hint = memories[0].decision if memories else "No prior diagnosis stored."
        summary = f"{agent_name} completed {stage} for task {task_id}. {prompt[:160]}"
        recommended_next = {
            "SpecInterpreter": "Review the structured plan and advance to PLAN.",
            "RTLAuthor": "Validate generated RTL and queue verification stages.",
            "Verifier": "Review verification notes and move into the next scheduled EDA stage.",
            "Diagnoser": "Inspect the diagnosis and retry the affected stage if needed.",
            "FlowAssistant": "Confirm orchestrator approval and continue the remaining DAG.",
        }[agent_name]

        diagnostics = [{
            "id": f"diag-{stage.lower()}",
            "title": f"{agent_name} summary for {stage}",
            "detail": f"Prior memory: {memory_hint}. Current context: {context}",
            "confidence": "High · deterministic graph execution",
            "primaryFile": self._primary_file(stage),
            "suggestedBy": agent_name,
        }]

        artifacts = [{
            "id": f"artifact-{stage.lower()}",
            "name": f"{stage.lower()}_summary.md",
            "type": "REPORT",
            "owner": agent_name,
        }]

        workspace_files: Dict[str, str] = {}
        if stage == "RTL_GEN":
            workspace_files["rtl/generated_top.v"] = self._rtl_template(task_id)
        elif stage in {"TB_GEN", "SIM"}:
            workspace_files["tb/generated_tb.sv"] = self._tb_template(task_id)
        elif stage == "FLOW_ASSISTANT":
            workspace_files["notes/orchestrator_patch.md"] = f"# Orchestrator patch\n\nPrompt: {prompt}\n\nNext step: {recommended_next}\n"
        else:
            workspace_files[f"reports/{stage.lower()}_notes.md"] = f"# {stage} notes\n\n{summary}\n"

        for tool_name in state.get("tools", []):
            if tool_name in self.tool_registry.tools:
                self.tool_registry.tools[tool_name](task_id=task_id, stage=stage, payload={"summary": summary, "agent": agent_name})

        state["result"] = AgentResult(
            agent_name=agent_name,
            summary=summary,
            diagnostics=diagnostics,
            artifacts=artifacts,
            workspace_files=workspace_files,
            recommended_next=recommended_next,
        )
        return state

    def persist_feedback(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result: AgentResult = state["result"]
        self.memory_store.save_memory(
            task_id=state.get("task_id", ""),
            stage=state.get("stage", "FLOW_ASSISTANT"),
            agent_name=result.agent_name,
            prompt=state.get("prompt", ""),
            decision=result.summary,
            diagnosis=result.diagnostics[0]["detail"] if result.diagnostics else "",
        )
        self.memory_store.write_diagnosis_to_redis(state.get("task_id", ""), {
            "agent": result.agent_name,
            "stage": state.get("stage", "FLOW_ASSISTANT"),
            "summary": result.summary,
            "recommended_next": result.recommended_next,
        })
        return state

    @staticmethod
    def _primary_file(stage: str) -> str:
        mapping = {
            "SPEC_INGEST": "spec/design_brief.md",
            "PLAN": "plans/execution_plan.md",
            "RTL_GEN": "rtl/generated_top.v",
            "TB_GEN": "tb/generated_tb.sv",
            "SIM": "reports/sim_notes.md",
            "LINT": "reports/lint_notes.md",
            "SYNTH": "reports/synth_notes.md",
            "PNR": "reports/pnr_notes.md",
            "DRC_LVS": "reports/drc_lvs_notes.md",
            "SIGNOFF": "reports/signoff_notes.md",
        }
        return mapping.get(stage, "notes/orchestrator_patch.md")

    @staticmethod
    def _rtl_template(task_id: str) -> str:
        return f"module generated_top #(parameter WIDTH = 32) (\n  input logic clk,\n  input logic rst_n,\n  input logic [WIDTH-1:0] data_i,\n  output logic [WIDTH-1:0] data_o\n);\n\n  always_ff @(posedge clk or negedge rst_n) begin\n    if (!rst_n) data_o <= '0;\n    else data_o <= data_i;\n  end\nendmodule\n// generated for {task_id}\n"

    @staticmethod
    def _tb_template(task_id: str) -> str:
        return f"module generated_tb;\n  initial begin\n    $display(\"Running smoke verification for {task_id}\");\n  end\nendmodule\n"
