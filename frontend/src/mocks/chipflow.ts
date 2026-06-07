import type {
  ApprovalPayload,
  ChipflowSnapshot,
  CreateTaskInput,
  ExportBundleResponse,
  ListTasksParams,
  ReviewGate,
  TaskDetail,
  TaskSummary,
  WaiverPayload,
  WorkflowStep,
} from '@/types/chipflow'

const STORAGE_KEY = 'chipflowai.mock.snapshot.v2'
const CURRENT_USER_ID = 'radhian.armansyah'
const CURRENT_USER_NAME = 'Radhian'

const workflowSteps: WorkflowStep[] = [
  {
    label: 'description',
    title: '1. Ingest spec',
    detail:
      'Prompt, markdown spec, prior RTL, or IP catalog references feed the task planner and retrieval layer.',
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

const seedSnapshot: ChipflowSnapshot = {
  workflowSteps,
  tasks: [
    {
      id: 'fft-1024p',
      name: 'FFT Accelerator 1024p',
      description: 'Streaming FFT block running through synthesis after passing simulation and lint.',
      ownerName: CURRENT_USER_NAME,
      ownerId: CURRENT_USER_ID,
      currentStage: 'Synthesis',
      etaLabel: '38 min',
      statusLabel: 'Running',
      tone: 'running',
      repoName: 'chipflowai/fft-accelerator-demo',
      mine: true,
    },
    {
      id: 'aes-refresh',
      name: 'AES-128 Core Refresh',
      description: 'Task-centric design object with artifact lineage',
      ownerName: 'Alice',
      ownerId: 'alice',
      currentStage: 'Lint rescue',
      etaLabel: '12 min',
      statusLabel: 'Needs review',
      tone: 'review',
      repoName: 'chipflowai/aes-core-refresh',
      needsReview: true,
    },
    {
      id: 'uart-lite',
      name: 'UART Controller Lite',
      description: 'Task-centric design object with artifact lineage',
      ownerName: 'Nadia',
      ownerId: 'nadia',
      currentStage: 'Signoff package',
      etaLabel: 'Ready',
      statusLabel: 'Passed',
      tone: 'passed',
      repoName: 'chipflowai/uart-lite',
    },
    {
      id: 'gpio-bridge',
      name: 'RISC-V GPIO Bridge',
      description: 'Task-centric design object with artifact lineage',
      ownerName: 'Ben',
      ownerId: 'ben',
      currentStage: 'Simulation',
      etaLabel: '19 min',
      statusLabel: 'Failed',
      tone: 'failed',
      repoName: 'chipflowai/gpio-bridge',
    },
  ],
  taskDetails: {
    'fft-1024p': {
      id: 'fft-1024p',
      name: 'FFT Accelerator 1024p',
      description:
        'Streaming FFT block running through synthesis after passing simulation and lint.',
      ownerName: CURRENT_USER_NAME,
      ownerId: CURRENT_USER_ID,
      currentStage: 'Synthesis',
      etaLabel: '38 min',
      statusLabel: 'Running',
      tone: 'running',
      repoName: 'chipflowai/fft-accelerator-demo',
      pdkLabel: 'Sky130 HD + SRAM macro pack',
      reviewGateLabel: 'Require engineer approval before synthesis and before signoff packaging',
      runtimeLabel: 'Agent + EDA pods',
      artifactLineageCount: 12,
      attempts: [{ id: 'attempt-4', status: 'running', startedAt: '09:12', updatedAt: '09:31' }],
      stages: [
        { key: 'spec-intake', label: 'Spec intake', status: 'done' },
        { key: 'agent-planning', label: 'Agent planning', status: 'done' },
        { key: 'verification-loop', label: 'Verification loop', status: 'done' },
        { key: 'implementation', label: 'Implementation', status: 'active' },
        { key: 'delivery', label: 'Delivery', status: 'queued' },
      ],
    },
    'aes-refresh': {
      id: 'aes-refresh',
      name: 'AES-128 Core Refresh',
      description: 'Task waiting on human review after lint rescue and staged timing fixes.',
      ownerName: 'Alice',
      ownerId: 'alice',
      currentStage: 'Lint rescue',
      etaLabel: '12 min',
      statusLabel: 'Needs review',
      tone: 'review',
      repoName: 'chipflowai/aes-core-refresh',
      pdkLabel: 'Sky130 default stack',
      reviewGateLabel: 'Review gate on lint waiver and retry',
      runtimeLabel: 'Lint and simulation pod',
      artifactLineageCount: 8,
      attempts: [{ id: 'attempt-2', status: 'pending approval', startedAt: '08:03', updatedAt: '08:48' }],
      stages: [
        { key: 'spec-intake', label: 'Spec intake', status: 'done' },
        { key: 'agent-planning', label: 'Agent planning', status: 'done' },
        { key: 'verification-loop', label: 'Verification loop', status: 'done', pendingApproval: true },
        { key: 'implementation', label: 'Implementation', status: 'queued' },
        { key: 'delivery', label: 'Delivery', status: 'queued' },
      ],
    },
    'uart-lite': {
      id: 'uart-lite',
      name: 'UART Controller Lite',
      description: 'Task has completed signoff packaging and is ready for delivery.',
      ownerName: 'Nadia',
      ownerId: 'nadia',
      currentStage: 'Signoff package',
      etaLabel: 'Ready',
      statusLabel: 'Passed',
      tone: 'passed',
      repoName: 'chipflowai/uart-lite',
      pdkLabel: 'GF180 reference flow',
      reviewGateLabel: 'Approval complete',
      runtimeLabel: 'Signoff packaging pod',
      artifactLineageCount: 16,
      attempts: [{ id: 'attempt-4', status: 'succeeded', startedAt: 'Yesterday', updatedAt: 'Today' }],
      stages: [
        { key: 'spec-intake', label: 'Spec intake', status: 'done' },
        { key: 'agent-planning', label: 'Agent planning', status: 'done' },
        { key: 'verification-loop', label: 'Verification loop', status: 'done' },
        { key: 'implementation', label: 'Implementation', status: 'done' },
        { key: 'delivery', label: 'Delivery', status: 'done' },
      ],
    },
    'gpio-bridge': {
      id: 'gpio-bridge',
      name: 'RISC-V GPIO Bridge',
      description: 'Task failed in simulation and is waiting on retry triage.',
      ownerName: 'Ben',
      ownerId: 'ben',
      currentStage: 'Simulation',
      etaLabel: '19 min',
      statusLabel: 'Failed',
      tone: 'failed',
      repoName: 'chipflowai/gpio-bridge',
      pdkLabel: 'Sky130 reference flow',
      reviewGateLabel: 'Human retry required',
      runtimeLabel: 'Simulation pod',
      artifactLineageCount: 5,
      attempts: [{ id: 'attempt-7', status: 'failed', startedAt: '11:04', updatedAt: '11:23' }],
      stages: [
        { key: 'spec-intake', label: 'Spec intake', status: 'done' },
        { key: 'agent-planning', label: 'Agent planning', status: 'done' },
        { key: 'verification-loop', label: 'Verification loop', status: 'failed' },
        { key: 'implementation', label: 'Implementation', status: 'queued' },
        { key: 'delivery', label: 'Delivery', status: 'queued' },
      ],
    },
  },
  events: {
    'fft-1024p': [
      {
        id: 'event-1',
        time: '09:12',
        title: 'Planner generated execution graph',
        detail: 'Split task into lint cleanup, synthesis staging, and waveform regression branches.',
        tone: 'info',
      },
      {
        id: 'event-2',
        time: '09:19',
        title: 'Simulation and lint closed cleanly',
        detail: 'Verification baseline was frozen and the task advanced into synthesis with manual review still enforced before signoff.',
        tone: 'warning',
      },
      {
        id: 'event-3',
        time: '09:31',
        title: 'Artifacts & reports versioned',
        detail: 'RTL diff, lint summary, timing trend, and handoff manifest were attached to the task object.',
        tone: 'success',
      },
    ],
  },
  artifacts: {
    'fft-1024p': [
      { id: 'artifact-1', name: 'fft_core.sv', type: 'RTL', owner: 'Workspace Agent' },
      { id: 'artifact-2', name: 'lint_summary.html', type: 'Report', owner: 'Verification Loop' },
      { id: 'artifact-3', name: 'timing_snapshot.json', type: 'Metric', owner: 'EDA Runtime' },
      { id: 'artifact-4', name: 'handoff_manifest.yaml', type: 'Delivery', owner: 'Signoff Agent' },
    ],
  },
  diagnoses: {
    'fft-1024p': [
      {
        id: 'diag-1',
        title: 'Review RTL diff before the next synthesis pass',
        detail:
          'Compare the latest FFT core update against the previous accepted revision, then rerun the verification slice before manual signoff review.',
        confidence: 'High · based on stable verification and improving WNS',
        primaryFile: 'rtl/fft_core.sv',
        suggestedBy: 'Verification loop agent',
      },
    ],
  },
  workspaceFiles: {
    'fft-1024p': [
      { path: 'rtl/fft_core.sv', name: 'fft_core.sv', note: 'Primary FFT core draft for synthesis handoff', status: 'RTL draft' },
      { path: 'tb/fft_core_tb.sv', name: 'fft_core_tb.sv', note: 'Regression suite with staged verification hooks', status: 'Healthy' },
      { path: 'constraints/constraints.sdc', name: 'constraints.sdc', note: 'Clock and IO timing constraints', status: 'Diff aware' },
    ],
  },
  workspaceContent: {
    'fft-1024p': {
      'rtl/fft_core.sv': `module fft_core #(
  parameter WIDTH = 16,
  parameter STAGES = 10
) (
  input  logic              clk,
  input  logic              rst_n,
  input  logic              valid_i,
  input  logic [WIDTH-1:0]  sample_re_i,
  input  logic [WIDTH-1:0]  sample_im_i,
  output logic              valid_o,
  output logic [WIDTH-1:0]  sample_re_o,
  output logic [WIDTH-1:0]  sample_im_o
);

// Next MVP action: review RTL diff and rerun verification
...`,
      'tb/fft_core_tb.sv': `module fft_core_tb;
  // Regression suite placeholder
endmodule`,
      'constraints/constraints.sdc': `create_clock -period 5 [get_ports clk]`,
    },
  },
  signoff: {
    'fft-1024p': {
      stateLabel: 'Awaiting final approval',
      message:
        'Export GDS, netlist, liberty views, constraints, reports, and design note generated from task history.',
      packageContents: [
        'GDS, netlist, timing, and waiver manifest',
        'Final RTL snapshot and verification report bundle',
        'Approval trail with owner and review metadata',
      ],
      checklist: [
        {
          id: 'check-1',
          label: 'DRC/LVS package ready',
          detail: 'Rule summaries, waivers, and ownership metadata bundled for review.',
          done: true,
        },
        {
          id: 'check-2',
          label: 'Power and timing guardrail accepted',
          detail: 'PPA deltas remain within agreed thresholds for the selected PDK corner set.',
          done: true,
        },
        {
          id: 'check-3',
          label: 'Tapeout handoff approved',
          detail: 'Awaiting final human review gate and release signature.',
          done: false,
        },
      ],
    },
  },
}

function cloneSnapshot(snapshot: ChipflowSnapshot): ChipflowSnapshot {
  return JSON.parse(JSON.stringify(snapshot)) as ChipflowSnapshot
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
  if (pdkId === 'sky130' && stdcellLibId === 'gf180-mixed-eval') {
    return 'Sky130 HD + SRAM macro pack'
  }

  return `${pdkId} / ${stdcellLibId}`
}

function getRepoName(task: CreateTaskInput['task']) {
  if (task.repo_mode === 'TEMPLATE') {
    return task.template_id ?? 'digital-block-starter'
  }

  return task.repo_id ?? 'Unspecified repo'
}

export function loadMockSnapshot(): ChipflowSnapshot {
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
    return JSON.parse(raw) as ChipflowSnapshot
  } catch {
    const snapshot = cloneSnapshot(seedSnapshot)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    return snapshot
  }
}

export function saveMockSnapshot(snapshot: ChipflowSnapshot) {
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
    runtimeLabel: 'EDA pod with synthesis + verification queue',
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
    description: 'Task-centric design object with artifact lineage',
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
