import type {
  ApprovalPayload,
  ChiporchestraSnapshot,
  CreateTaskInput,
  ExportBundleResponse,
  ListTasksParams,
  ReviewGate,
  TaskDetail,
  TaskSummary,
  WaiverPayload,
  WorkflowStep,
} from '@/types/chiporchestra'

const STORAGE_KEY = 'chiporchestra.mock.snapshot.v3'
const CURRENT_USER_ID = 'engineer'
const CURRENT_USER_NAME = 'Engineer'

// The 5-step RTL-to-GDS strip shown on the Overview console. This is real product
// copy (not placeholder task data), so it is kept even when mocks are disabled.
const workflowSteps: WorkflowStep[] = [
  {
    label: 'description',
    title: '1. Ingest spec',
    detail:
      'A natural-language design brief feeds the task planner and the web-research / RAG retrieval layer.',
    tone: 'violet',
  },
  {
    label: 'smart_toy',
    title: '2. Agent plan',
    detail:
      'Agents break work into RTL, testbench, constraints, and optimization subtasks with explicit dependencies.',
    tone: 'mint',
  },
  {
    label: 'experiment',
    title: '3. Verify loop',
    detail: 'Simulation, lint, and debug outputs stream back to the task detail view for iteration.',
    tone: 'sky',
  },
  {
    label: 'deployed_code',
    title: '4. Implement',
    detail: 'Synthesis and implementation stages reuse the same task construct, artifacts, and observability pattern.',
    tone: 'amber',
  },
  {
    label: 'inventory_2',
    title: '5. Deliver',
    detail: 'Package GDS, reports, waivers, docs, and approval state into a signoff-ready handoff object.',
    tone: 'rose',
  },
]

// No seed tasks: the app runs against the real backend. The mock layer only
// provides offline fallback state when VITE_USE_MOCKS=true.
const seedSnapshot: ChiporchestraSnapshot = {
  workflowSteps,
  tasks: [],
  taskDetails: {},
  events: {},
  artifacts: {},
  diagnoses: {},
  workspaceFiles: {},
  workspaceContent: {},
  signoff: {},
}

function cloneSnapshot(snapshot: ChiporchestraSnapshot): ChiporchestraSnapshot {
  return JSON.parse(JSON.stringify(snapshot)) as ChiporchestraSnapshot
}

function formatReviewGateLabel(reviewGates: ReviewGate[]) {
  if (reviewGates.includes('BEFORE_SYNTH') && reviewGates.includes('BEFORE_SIGNOFF')) {
    return 'Require engineer approval before synthesis and before signoff packaging'
  }

  if (reviewGates.includes('BEFORE_SYNTH')) {
    return 'Require engineer approval before synthesis'
  }

  return 'Require engineer approval before signoff packaging'
}

function formatPdkLabel(pdkId: string, stdcellLibId: string) {
  if (pdkId.startsWith('sky130')) return 'Sky130 HD'
  if (pdkId.startsWith('gf180')) return 'GF180MCU'
  return `${pdkId} / ${stdcellLibId}`
}

function getRepoName(task: CreateTaskInput['task']) {
  if (task.repo_mode === 'TEMPLATE') {
    return task.template_id ?? 'digital-block-starter'
  }

  return task.repo_id ?? 'Unspecified repo'
}

export function loadMockSnapshot(): ChiporchestraSnapshot {
  if (typeof window === 'undefined') {
    return cloneSnapshot(seedSnapshot)
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    const snapshot = cloneSnapshot(seedSnapshot)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    return snapshot
  }

  try {
    return JSON.parse(raw) as ChiporchestraSnapshot
  } catch {
    const snapshot = cloneSnapshot(seedSnapshot)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    return snapshot
  }
}

export function saveMockSnapshot(snapshot: ChiporchestraSnapshot) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
}

export function filterMockTasks(tasks: TaskSummary[], params: ListTasksParams = {}) {
  return tasks.filter((task) => {
    if (params.owner && params.owner !== 'me' && task.ownerId !== params.owner) return false
    if (params.owner === 'me' && task.ownerId !== CURRENT_USER_ID) return false
    if (params.failed && task.tone !== 'failed') return false
    if (params.needs_review && !task.needsReview && task.tone !== 'review') return false
    if (params.stage && task.currentStage !== params.stage) return false
    if (params.status && task.statusLabel !== params.status) return false
    if (params.repo && !task.repoName.toLowerCase().includes(params.repo.toLowerCase())) return false
    return true
  })
}

export function createMockTask(input: CreateTaskInput): TaskDetail {
  const snapshot = loadMockSnapshot()
  const task = input.task
  const id = `${task.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${Date.now().toString(36)}`
  const repoName = getRepoName(task)
  const reviewGateLabel = formatReviewGateLabel(task.review_gates)

  const detail: TaskDetail = {
    id,
    name: task.name,
    description: task.design_brief,
    ownerName: task.owner_name ?? CURRENT_USER_NAME,
    ownerId: task.owner_id ?? CURRENT_USER_ID,
    currentStage: 'Spec intake',
    etaLabel: 'Queued',
    statusLabel: 'Running',
    tone: 'running',
    repoName,
    pdkLabel: formatPdkLabel(task.pdk_id, task.stdcell_lib_id),
    reviewGateLabel,
    runtimeLabel: 'Agent + EDA pods',
    artifactLineageCount: 0,
    attempts: [{ id: `attempt-${Date.now().toString(36)}`, status: 'queued', startedAt: 'Just now', updatedAt: 'Just now' }],
    stages: [
      { key: 'spec-intake', label: 'Spec intake', status: 'active' },
      { key: 'agent-planning', label: 'Agent planning', status: 'queued' },
      { key: 'verification-loop', label: 'Verification loop', status: 'queued' },
      { key: 'implementation', label: 'Implementation', status: 'queued' },
      { key: 'delivery', label: 'Delivery', status: 'queued' },
    ],
  }

  snapshot.tasks.unshift({
    id,
    name: detail.name,
    description: detail.description,
    ownerName: detail.ownerName,
    ownerId: detail.ownerId,
    currentStage: detail.currentStage,
    etaLabel: detail.etaLabel,
    statusLabel: detail.statusLabel,
    tone: detail.tone,
    repoName: detail.repoName,
    mine: detail.ownerId === CURRENT_USER_ID,
  })
  snapshot.taskDetails[id] = detail
  snapshot.events[id] = [
    {
      id: `event-${id}`,
      time: 'Now',
      title: 'Task created',
      detail: 'The task has been enqueued with the selected repo, environment, and review gate.',
      tone: 'info',
    },
  ]
  snapshot.artifacts[id] = []
  snapshot.diagnoses[id] = []
  snapshot.workspaceFiles[id] = []
  snapshot.workspaceContent[id] = {}
  snapshot.signoff[id] = {
    stateLabel: 'Not started',
    message: 'Signoff will be available once verification and implementation phases complete.',
    packageContents: ['Signoff bundle will be generated after implementation'],
    checklist: [
      { id: `${id}-signoff-1`, label: 'DRC/LVS package ready', detail: 'Pending run completion.', done: false },
      { id: `${id}-signoff-2`, label: 'Power and timing guardrail accepted', detail: 'Pending verification.', done: false },
      { id: `${id}-signoff-3`, label: 'Tapeout handoff approved', detail: 'Pending approval.', done: false },
    ],
  }

  saveMockSnapshot(snapshot)
  return detail
}

export function applyMockApproval(taskId: string, _stage: string, payload: ApprovalPayload) {
  const snapshot = loadMockSnapshot()
  const signoff = snapshot.signoff[taskId]
  if (!signoff) return

  signoff.stateLabel = payload.decision === 'approve' ? 'Approved' : 'Needs follow-up'
  signoff.message =
    payload.decision === 'approve'
      ? 'Approval has been recorded. The task can move into export packaging.'
      : 'Approval was rejected. Review the diagnosis and rerun the required stages.'

  if (payload.decision === 'approve') {
    signoff.checklist = signoff.checklist.map((item, index) =>
      index === signoff.checklist.length - 1 ? { ...item, done: true } : item,
    )
  }

  saveMockSnapshot(snapshot)
}

export function applyMockWaiver(taskId: string, payload: WaiverPayload) {
  const snapshot = loadMockSnapshot()
  snapshot.events[taskId] = [
    {
      id: `waiver-${Date.now().toString(36)}`,
      time: 'Now',
      title: `Waiver requested: ${payload.title}`,
      detail: payload.detail,
      tone: 'warning',
    },
    ...(snapshot.events[taskId] ?? []),
  ]
  saveMockSnapshot(snapshot)
}

export function createMockExportBundle(taskId: string): ExportBundleResponse {
  const snapshot = loadMockSnapshot()
  snapshot.events[taskId] = [
    {
      id: `export-${Date.now().toString(36)}`,
      time: 'Now',
      title: 'Export bundle requested',
      detail: 'A delivery bundle artifact has been queued for packaging.',
      tone: 'success',
    },
    ...(snapshot.events[taskId] ?? []),
  ]
  saveMockSnapshot(snapshot)

  return {
    artifactId: `bundle-${Date.now().toString(36)}`,
    status: 'queued',
  }
}
