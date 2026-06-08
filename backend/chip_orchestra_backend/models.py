"""Pydantic models that mirror the frontend's domain types 1:1.

Response models use the exact camelCase field names the frontend's
`src/types/chiporchestra.ts` reads. The create-task request uses the snake_case
shape the frontend's `src/api/tasks.ts` sends.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Shared enums (kept loose so the agent can introduce nuance) -------------
StageTone = Literal["running", "review", "passed", "failed"]
WorkflowTone = Literal["mint", "sky", "amber", "rose", "violet"]
EventTone = Literal["info", "success", "warning"]
TimelineState = Literal["done", "active", "queued", "failed"]
LaunchMode = Literal["FULL_FLOW_GATED", "GEN_ONLY", "VERIFY_RESCUE", "SYNTH_ONLY"]
RepoMode = Literal["EXISTING", "TEMPLATE"]
ReviewGate = Literal["BEFORE_SYNTH", "BEFORE_SIGNOFF"]
AgentAutonomyLevel = Literal["LOW", "BALANCED", "HIGH"]
ResearchDepth = Literal["SMALL", "MEDIUM", "DEEP"]


# --- Response models (camelCase, consumed by the frontend) ------------------
class WorkflowStep(BaseModel):
    label: str
    title: str
    detail: str
    tone: WorkflowTone


class TaskSummary(BaseModel):
    id: str
    name: str
    description: str
    ownerName: str
    ownerId: str
    currentStage: str
    etaLabel: str
    statusLabel: str
    tone: StageTone
    repoName: str
    needsReview: bool | None = None
    mine: bool | None = None


class TaskStage(BaseModel):
    key: str
    label: str
    status: TimelineState
    pendingApproval: bool | None = None
    waiverReviewPending: bool | None = None


class TaskAttempt(BaseModel):
    id: str
    status: str
    startedAt: str
    updatedAt: str


class TaskDetail(BaseModel):
    id: str
    name: str
    description: str
    ownerName: str
    ownerId: str
    currentStage: str
    etaLabel: str
    statusLabel: str
    tone: StageTone
    repoName: str
    pdkLabel: str
    reviewGateLabel: str
    runtimeLabel: str
    artifactLineageCount: int
    stages: list[TaskStage]
    attempts: list[TaskAttempt]


class RunbookEvent(BaseModel):
    id: str
    time: str
    title: str
    detail: str
    tone: EventTone


class ArtifactItem(BaseModel):
    id: str
    name: str
    type: str
    owner: str


class DiagnosisItem(BaseModel):
    id: str
    title: str
    detail: str
    confidence: str
    primaryFile: str
    suggestedBy: str


class WorkspaceFileSummary(BaseModel):
    path: str
    name: str
    note: str
    status: str


class WorkspaceFileContent(BaseModel):
    path: str
    content: str


class SignoffChecklistItem(BaseModel):
    id: str
    label: str
    detail: str
    done: bool


class SignoffStatus(BaseModel):
    stateLabel: str
    message: str
    packageContents: list[str]
    checklist: list[SignoffChecklistItem]


class ExportBundleResponse(BaseModel):
    artifactId: str
    status: str


class StatusResponse(BaseModel):
    status: str


# --- Request models (snake_case, sent by the frontend) ----------------------
class AgentPolicy(BaseModel):
    autonomy_level: AgentAutonomyLevel = "BALANCED"
    retry_budget: int = 2
    auto_apply_patches: bool = True


class CreateTaskPayload(BaseModel):
    name: str
    launch_mode: LaunchMode = "FULL_FLOW_GATED"
    design_brief: str
    repo_id: str | None = None
    repo_branch: str | None = None
    repo_mode: RepoMode = "TEMPLATE"
    template_id: str | None = None
    pdk_id: str = "sky130"
    stdcell_lib_id: str = "sky130_fd_sc_hd"
    review_gates: list[ReviewGate] = Field(default_factory=lambda: ["BEFORE_SYNTH", "BEFORE_SIGNOFF"])
    agent_policy: AgentPolicy = Field(default_factory=AgentPolicy)
    owner_id: str | None = None
    owner_name: str | None = None
    # Optional per-task LLM override (ignored unless provided).
    model: str | None = None
    # Optional hardening hint: clock period in ns for the constraints file.
    clock_period_ns: float | None = None
    # Web-research depth: SMALL (3+3), MEDIUM (6+6), DEEP (10+10 GitHub+web).
    research_depth: ResearchDepth = "MEDIUM"


class CreateTaskInput(BaseModel):
    task: CreateTaskPayload


class ApprovalPayload(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str | None = None


class WaiverPayload(BaseModel):
    title: str
    detail: str


class ProposePatchPayload(BaseModel):
    instruction: str
