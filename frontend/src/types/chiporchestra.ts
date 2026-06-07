export type NavView = 'overview' | 'create' | 'detail'
export type TaskFilter = 'all' | 'mine' | 'review' | 'failed'
export type StageTone = 'running' | 'review' | 'passed' | 'failed'
export type WorkflowTone = 'mint' | 'sky' | 'amber' | 'rose' | 'violet'
export type EventTone = 'info' | 'success' | 'warning'
export type TimelineState = 'done' | 'active' | 'queued' | 'failed'
export type LaunchMode = 'FULL_FLOW_GATED' | 'GEN_ONLY' | 'VERIFY_RESCUE' | 'SYNTH_ONLY'
export type RepoMode = 'EXISTING' | 'TEMPLATE'
export type ReviewGate = 'BEFORE_SYNTH' | 'BEFORE_SIGNOFF'
export type AgentAutonomyLevel = 'LOW' | 'BALANCED' | 'HIGH'

export interface WorkflowStep {
  label: string
  title: string
  detail: string
  tone: WorkflowTone
}

export interface TaskSummary {
  id: string
  name: string
  description: string
  ownerName: string
  ownerId: string
  currentStage: string
  etaLabel: string
  statusLabel: string
  tone: StageTone
  repoName: string
  needsReview?: boolean
  mine?: boolean
}

export interface TaskStage {
  key: string
  label: string
  status: TimelineState
  pendingApproval?: boolean
  waiverReviewPending?: boolean
}

export interface TaskAttempt {
  id: string
  status: string
  startedAt: string
  updatedAt: string
}

export interface TaskDetail {
  id: string
  name: string
  description: string
  ownerName: string
  ownerId: string
  currentStage: string
  etaLabel: string
  statusLabel: string
  tone: StageTone
  repoName: string
  pdkLabel: string
  reviewGateLabel: string
  runtimeLabel: string
  artifactLineageCount: number
  stages: TaskStage[]
  attempts: TaskAttempt[]
}

export interface RunbookEvent {
  id: string
  time: string
  title: string
  detail: string
  tone: EventTone
}

export interface ArtifactItem {
  id: string
  name: string
  type: string
  owner: string
}

export interface DiagnosisItem {
  id: string
  title: string
  detail: string
  confidence: string
  primaryFile: string
  suggestedBy: string
}

export interface WorkspaceFileSummary {
  path: string
  name: string
  note: string
  status: string
}

export interface WorkspaceFileContent {
  path: string
  content: string
}

export interface SignoffChecklistItem {
  id: string
  label: string
  detail: string
  done: boolean
}

export interface SignoffStatus {
  stateLabel: string
  message: string
  packageContents: string[]
  checklist: SignoffChecklistItem[]
}

export interface AgentPolicy {
  autonomy_level: AgentAutonomyLevel
  retry_budget: number
  auto_apply_patches: boolean
}

export interface CreateTaskPayload {
  name: string
  launch_mode: LaunchMode
  design_brief: string
  repo_id?: string
  repo_branch?: string
  repo_mode: RepoMode
  template_id?: string
  pdk_id: string
  stdcell_lib_id: string
  review_gates: ReviewGate[]
  agent_policy: AgentPolicy
  owner_id?: string
  owner_name?: string
}

export interface CreateTaskInput {
  task: CreateTaskPayload
}

export interface ListTasksParams {
  owner?: string
  status?: string
  stage?: string
  repo?: string
  needs_review?: boolean
  failed?: boolean
}

export interface ApprovalPayload {
  decision: 'approve' | 'reject'
  comment?: string
}

export interface WaiverPayload {
  title: string
  detail: string
}

export interface ExportBundleResponse {
  artifactId: string
  status: string
}

export interface ChiporchestraSnapshot {
  tasks: TaskSummary[]
  workflowSteps: WorkflowStep[]
  taskDetails: Record<string, TaskDetail>
  events: Record<string, RunbookEvent[]>
  artifacts: Record<string, ArtifactItem[]>
  diagnoses: Record<string, DiagnosisItem[]>
  workspaceFiles: Record<string, WorkspaceFileSummary[]>
  workspaceContent: Record<string, Record<string, string>>
  signoff: Record<string, SignoffStatus>
}
