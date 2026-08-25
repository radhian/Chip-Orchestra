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

/** One die signal and the pad it lands on (die <-> pad-ring bring-up map). */
export interface PinoutEntry {
  signal: string
  pad_instance: string
  pad_pin: string
  pad_master: string
  direction: string
  side: string
  x: number | null
  y: number | null
}

export interface SignoffStatus {
  stateLabel: string
  message: string
  packageContents: string[]
  checklist: SignoffChecklistItem[]
  gdsImage?: string
  gdsFiles?: string[]
  metrics?: Record<string, string | number | boolean | null>
  pinout?: PinoutEntry[]
}

/** One thing the golden model produced that the reviewer should look at. */
export interface GoldenPreview {
  kind: 'image' | 'waveform' | 'value'
  path: string
  label: string
}

export interface GoldenIP {
  name: string
  file?: string
  /** 'ip' (leaf block) | 'subtop' (integrator) | 'top' (chip) */
  tier?: string
  role?: string
  ports?: string
}

export interface GoldenTestResults {
  ran?: boolean
  total?: number
  passed?: number
  failed?: number
  files?: string[]
}

export interface GoldenSummary {
  top?: string
  design_brief?: string
  ips?: GoldenIP[]
  models?: string[]
  vectors?: string[]
  tests?: GoldenTestResults
  previews?: GoldenPreview[]
  notes?: string
  report?: string
  contract?: string
}

/** Payload behind the GOLDEN_GEN review dialog: what the Python reference model
 *  computed, whether its own test suite passed, and whether the gate is open. */
export interface GoldenReview {
  stage: string
  status: string
  awaitingApproval: boolean
  available: boolean
  summary: GoldenSummary
  report: string
  testLog: string
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
  voltage?: string
  padring?: string
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

export interface SimPreview {
  path: string
  label: string
  /** 'input' | 'golden' (desired) | 'chip' (actual) | 'waveform' */
  role: string
}

export interface SimReport {
  summary?: string
  errors?: string[]
  warnings?: string[]
  metrics?: Record<string, unknown>
  artifacts?: Array<{ path?: string; kind?: string }>
}

/** Payload behind the SIM review dialog: what the CHIP computed versus what the
 *  golden model said it should, plus the testbench console. SIM is the last
 *  cheap place to change the design — everything after it hardens whatever the
 *  RTL already does. */
export interface SimReview {
  stage: string
  status: string
  awaitingApproval: boolean
  available: boolean
  report: SimReport
  simLog: string
  previews: SimPreview[]
  goldenMatch: boolean
  hasGoldenMatch: boolean
}

/** One of the two generated halves of the hardware/software bridge — the Python
 *  host driver or the Verilog interface bench — shown so the reviewer can read
 *  the code that produced the result, not just the result. */
export interface HwSwSource {
  path: string
  label: string
  content: string
}

export interface HwSwInterface {
  kind?: string
  description?: string
  clock?: string
  reset?: string
  data_in?: string[]
  data_out?: string[]
  baud_div?: number
  constants?: Record<string, number>
  driver?: string
  testbench?: string
  driver_origin?: string
  testbench_origin?: string
}

export interface HwSwReport {
  stage?: string
  top?: string
  summary?: string
  completed?: boolean
  input?: { path?: string; name?: string; bytes_in?: number; bytes_out?: number }
  interface?: HwSwInterface
  metrics?: Record<string, unknown>
  first_mismatch?: { index?: number; chip?: number; expected?: number } | null
  previews?: string[]
  errors?: string[]
}

/** Payload behind the HW/SW verification dialog: what the chip returned when the
 *  host driver sent it a real input over the chip's real interface, next to what
 *  the golden model says it should have returned. */
export interface HwSwReview {
  stage: string
  status: string
  awaitingApproval: boolean
  available: boolean
  report: HwSwReport
  consoleLog: string
  previews: SimPreview[]
  sources: HwSwSource[]
  inputName: string
  match: boolean
  hasMatch: boolean
}
