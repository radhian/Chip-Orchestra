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

export interface UserProfile {
  id: string
  username: string
  fullName: string
  roles: string[]
}

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
  retryCount?: number
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
  /** Full RFC3339 timestamp — preferred over `time` (which is server-local). */
  timestamp?: string
  title: string
  detail: string
  tone: EventTone
  /** Optional workspace-relative image to render under the event
   *  (uploaded diagram, GDS layout render). */
  image?: string
}

export interface ArtifactItem {
  id: string
  name: string
  type: string
  owner: string
  url?: string
  path?: string
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
  status?: 'done' | 'pending' | 'failed'
}

export interface SignoffStatus {
  stateLabel: string
  message: string
  packageContents: string[]
  checklist: SignoffChecklistItem[]
  gdsImage?: string
  gdsFiles?: string[]
  metrics?: Record<string, string | number | boolean | null>
}

export interface AgentPolicy {
  autonomy_level: AgentAutonomyLevel
  retry_budget: number
  auto_apply_patches: boolean
}

export interface CreateTaskPayload {
  name: string
  description?: string
  launch_mode: LaunchMode
  design_brief: string
  repo_id?: string
  repo_branch?: string
  repo_mode: RepoMode
  template_id?: string
  pdk_id: string
  stdcell_lib_id: string
  llm_model?: string
  review_gates: ReviewGate[]
  agent_policy: AgentPolicy
  owner_id?: string
  owner_name?: string
  attachments?: TaskAttachment[]
}

export interface TaskAttachment {
  name: string
  content_base64: string
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
  page?: number
  page_size?: number
  search?: string
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
