import type { ComponentType } from 'react'
import { NavLink } from 'react-router-dom'
import { AlertCircle, Ban, CheckCircle2, Clock3, FileCode2, ListChecks, PackageCheck, Pause, Play, RotateCcw } from 'lucide-react'

import type {
  ArtifactItem,
  DiagnosisItem,
  RunbookEvent,
  SignoffStatus,
  StageTone,
  TaskDetail,
  TimelineState,
  WorkspaceFileSummary,
} from '@/types/chiporchestra'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ChecklistCard, MaterialIcon, MiniPanel, StagePill } from '@/components/app/PlatformTaskPrimitives'

type PillTone = 'running' | 'done' | 'review' | 'neutral' | 'failed'

// Map the real backend stage status -> pill tone, label, and a short note.
const STAGE_TONE: Record<TimelineState, PillTone> = {
  done: 'done',
  active: 'running',
  queued: 'neutral',
  failed: 'failed',
}
const STAGE_LABEL: Record<TimelineState, string> = {
  done: 'Done',
  active: 'Active',
  queued: 'Queued',
  failed: 'Failed',
}
const STAGE_NOTE: Record<TimelineState, string> = {
  done: 'Complete',
  active: 'In progress',
  queued: 'Queued',
  failed: 'Needs attention',
}
const STAGE_PROGRESS: Record<TimelineState, number> = { done: 100, active: 55, failed: 100, queued: 8 }
const STAGE_BAR: Record<TimelineState, string> = {
  done: 'bg-[#10b981]',
  active: 'bg-[#2563eb]',
  failed: 'bg-[#d4495a]',
  queued: 'bg-slate-300',
}
// Map the task's headline tone (StageTone) -> pill tone.
const STATUS_TONE: Record<StageTone, PillTone> = {
  running: 'running',
  review: 'review',
  passed: 'done',
  failed: 'failed',
}

type DetailTab = 'runbook' | 'rtl' | 'signoff'

export function PlatformTaskSections({
  task,
  artifacts,
  diagnoses,
  events,
  files,
  selectedFile,
  selectedFileContent,
  signoff,
  activeTab,
  onSelectFile,
  onStop,
  onResume,
  onCancel,
  onRetry,
}: {
  task: TaskDetail
  artifacts: ArtifactItem[]
  diagnoses: DiagnosisItem[]
  events: RunbookEvent[]
  files: WorkspaceFileSummary[]
  selectedFile: string
  selectedFileContent: string
  signoff: SignoffStatus | null
  activeTab: DetailTab
  onSelectFile: (path: string) => void
  onStop?: () => void
  onResume?: () => void
  onCancel?: () => void
  onRetry?: () => void
}) {
  const primaryDiagnosis = diagnoses[0]
  const attemptLabel = task.attempts[0]?.id?.replace('attempt-', 'Attempt #') ?? 'Attempt #1'
  const isActive = task.statusLabel === 'Running'
  const isPaused = task.statusLabel === 'Paused'
  const isPending = task.statusLabel === 'Stopping' || task.statusLabel === 'Cancelling'
  const isRetryable = ['Failed', 'Interrupted', 'Cancelled'].includes(task.statusLabel)
  const canCancel = !['Passed', 'Cancelled'].includes(task.statusLabel)
  const showControls = isActive || isPaused || isPending || isRetryable
  const stageColsClass =
    task.stages.length >= 5 ? 'xl:grid-cols-5' : task.stages.length === 4 ? 'xl:grid-cols-4' : 'xl:grid-cols-3'

  const verificationRows = (
    [
      ['verification-loop', 'Verification loop'],
      ['implementation', 'Implementation'],
      ['delivery', 'Delivery'],
    ] as const
  ).map(([key, label]) => ({
    label,
    status: (task.stages.find((s) => s.key === key)?.status ?? 'queued') as TimelineState,
  }))

  return (
    <section className='space-y-5'>
      <Card className='rounded-[28px] border border-slate-200 shadow-none'>
        <CardContent className='space-y-5 p-6'>
          <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
            <div>
              <p className='text-sm font-medium text-slate-400'>Selected task</p>
              <h3 className='mt-2 text-[2rem] font-semibold tracking-tight text-slate-900'>{task.name}</h3>
              <p className='mt-2 text-sm leading-6 text-slate-500'>{task.description}</p>
            </div>
            <div className='flex flex-col items-start gap-3 xl:items-end'>
              <div className='flex flex-wrap items-center gap-2'>
                <StagePill label={task.statusLabel} tone={STATUS_TONE[task.tone]} />
                <StagePill label={attemptLabel} tone='neutral' />
                {task.tone === 'review' ? <StagePill label='Manual review' tone='review' /> : null}
              </div>
              {showControls ? (
                <div className='flex flex-wrap items-center gap-2'>
                  {isActive && onStop ? <ControlButton icon={Pause} label='Stop' onClick={onStop} /> : null}
                  {isPaused && onResume ? (
                    <ControlButton icon={Play} label='Resume' onClick={onResume} tone='primary' />
                  ) : null}
                  {isRetryable && onRetry ? (
                    <ControlButton icon={RotateCcw} label='Retry' onClick={onRetry} tone='primary' />
                  ) : null}
                  {canCancel && onCancel ? (
                    <ControlButton icon={Ban} label='Cancel' onClick={onCancel} tone='danger' />
                  ) : null}
                  {isPending ? (
                    <span className='text-sm font-medium text-slate-400'>{task.statusLabel}…</span>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>

          <div className={`grid gap-3 grid-cols-2 md:grid-cols-3 ${stageColsClass}`}>
            {task.stages.map((stage) => {
              const active = stage.status === 'active'
              const failed = stage.status === 'failed'
              return (
                <div
                  key={stage.key}
                  className={`rounded-[22px] border px-4 py-5 text-center ${
                    active
                      ? 'border-[#cbd5ff] bg-[#eef2ff]'
                      : failed
                        ? 'border-[#f3c9cf] bg-[#fdf0f1]'
                        : 'border-slate-200 bg-white'
                  }`}
                >
                  <p className='text-sm font-semibold text-slate-800'>{stage.label}</p>
                  <p className='mt-2 text-xs text-slate-500'>
                    {stage.pendingApproval ? 'Awaiting approval' : STAGE_NOTE[stage.status]}
                  </p>
                  <div className='mt-4 flex justify-center'>
                    <StagePill label={STAGE_LABEL[stage.status]} tone={STAGE_TONE[stage.status]} />
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <div className='grid h-auto w-full grid-cols-3 rounded-[22px] bg-slate-100 p-1'>
        <DetailRouteTab to={`/tasks/${task.id}`} label='Runbook' icon='list_alt' active={activeTab === 'runbook'} />
        <DetailRouteTab to={`/tasks/${task.id}/rtl`} label='RTL Workspace' icon='terminal' active={activeTab === 'rtl'} />
        <DetailRouteTab
          to={`/tasks/${task.id}/signoff`}
          label='Signoff & Delivery'
          icon='verified'
          active={activeTab === 'signoff'}
        />
      </div>

      <div className='rounded-[22px] bg-[#eef0ff] px-4 py-3 text-sm font-medium text-[#5b5bd6]'>
        <div className='flex items-start gap-2'>
          <MaterialIcon name='account_tree' className='mt-0.5 text-[18px]' />
          <p>These views are scoped to the currently selected task, so RTL changes and signoff decisions remain independent per design run.</p>
        </div>
      </div>

      {activeTab === 'runbook' ? (
        <div className='grid gap-4 xl:grid-cols-3'>
          <MiniPanel title='Execution log' subtitle='Stage-aware logs instead of a single opaque terminal' badge={task.currentStage}>
            {events.length === 0 ? <p className='text-sm text-slate-400'>Waiting for the first agent step…</p> : null}
            {events.slice(0, 4).map((event) => (
              <div key={event.id} className='rounded-[18px] bg-slate-50 p-4'>
                <p className='text-xs font-semibold uppercase tracking-[0.18em] text-slate-400'>{event.time}</p>
                <p className='mt-2 font-semibold text-slate-900'>{event.title}</p>
                <p className='mt-2 text-sm leading-6 text-slate-500'>{event.detail}</p>
              </div>
            ))}
          </MiniPanel>

          <MiniPanel title='Artifacts & reports' subtitle='Every stage emits inspectable assets' badge='Versioned'>
            {artifacts.slice(0, 3).map((artifact) => (
              <div key={artifact.id} className='flex items-center justify-between rounded-[18px] bg-slate-50 p-4'>
                <div>
                  <p className='font-semibold text-slate-900'>{artifact.name}</p>
                  <p className='mt-1 text-sm text-slate-500'>{artifact.type} · {artifact.owner}</p>
                </div>
                <MaterialIcon name='open_in_new' className='text-[18px] text-slate-400' />
              </div>
            ))}
          </MiniPanel>

          <MiniPanel
            title='AI diagnosis'
            subtitle='Suggested next actions stay explainable'
            badge={diagnoses.length ? `${diagnoses.length} recommendation${diagnoses.length === 1 ? '' : 's'}` : 'No findings'}
          >
            {primaryDiagnosis ? (
              <div className='space-y-3'>
                <div className='rounded-[18px] border border-amber-200 bg-amber-50 p-4'>
                  <div className='flex items-center gap-2 text-amber-700'>
                    <AlertCircle className='h-4 w-4' />
                    <p className='font-semibold'>{primaryDiagnosis.title}</p>
                  </div>
                  <p className='mt-2 text-sm leading-6 text-amber-900/80'>{primaryDiagnosis.detail}</p>
                </div>
                <div className='rounded-[18px] bg-slate-50 p-4 text-sm leading-6 text-slate-600'>
                  Confidence: {primaryDiagnosis.confidence} · {primaryDiagnosis.suggestedBy}
                </div>
              </div>
            ) : (
              <p className='text-sm text-slate-400'>No diagnosis yet — the agent reports findings when a stage needs attention.</p>
            )}
          </MiniPanel>
        </div>
      ) : null}

      {activeTab === 'rtl' ? (
        <div className='grid gap-5 xl:grid-cols-[1.35fr_.65fr]'>
          <Card className='rounded-[28px] border border-slate-200 shadow-none'>
            <CardHeader className='pb-4'>
              <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between'>
                <div>
                  <CardTitle className='text-[1.4rem] text-slate-900'>RTL workspace for {task.name}</CardTitle>
                  <p className='mt-2 text-sm leading-6 text-slate-500'>This editing and review context belongs to the current task only.</p>
                </div>
                <div className='flex gap-2'>
                  <StagePill label='RTL draft' tone='running' />
                  <StagePill label='Diff aware' tone='neutral' />
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='flex flex-wrap gap-2'>
                {files.map((file) => (
                  <button
                    key={file.path}
                    type='button'
                    onClick={() => onSelectFile(file.path)}
                    className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                      file.path === selectedFile ? 'bg-[#ecebff] text-[#5b5bd6]' : 'bg-slate-100 text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {file.name}
                  </button>
                ))}
              </div>

              <div className='overflow-hidden rounded-[24px] border border-slate-200 bg-[#fbfdff]'>
                <div className='grid grid-cols-[44px_1fr]'>
                  <div className='border-r border-slate-200 bg-[#f1f5f9] px-3 py-4 text-right text-xs leading-7 text-slate-400'>
                    {Array.from({ length: 14 }, (_, index) => (
                      <div key={index}>{index + 1}</div>
                    ))}
                  </div>
                  <div className='p-4'>
                    <div className='flex items-center gap-2 text-sm text-slate-400'>
                      <FileCode2 className='h-4 w-4' />
                      {selectedFile}
                    </div>
                    <pre className='mt-3 overflow-x-auto text-sm leading-7 text-slate-700'>{selectedFileContent}</pre>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className='rounded-[28px] border border-slate-200 shadow-none'>
            <CardHeader>
              <CardTitle className='text-[1.4rem] text-slate-900'>Verification status</CardTitle>
            </CardHeader>
            <CardContent className='space-y-5'>
              {verificationRows.map((row) => (
                <div key={row.label}>
                  <div className='mb-2 flex items-center justify-between gap-3'>
                    <p className='text-sm font-medium text-slate-600'>{row.label}</p>
                    <span className='text-sm font-semibold text-slate-500'>{STAGE_LABEL[row.status]}</span>
                  </div>
                  <Progress
                    value={STAGE_PROGRESS[row.status]}
                    indicatorClassName={STAGE_BAR[row.status]}
                    className='h-2.5 bg-slate-100'
                  />
                </div>
              ))}

              <div className='rounded-[22px] bg-slate-50 p-4'>
                <div className='space-y-3'>
                  {files.map((file) => (
                    <div key={file.path} className='flex items-center justify-between rounded-[16px] bg-white px-4 py-3'>
                      <div>
                        <p className='font-semibold text-slate-900'>{file.name}</p>
                        <p className='mt-1 text-sm text-slate-500'>{file.note}</p>
                      </div>
                      <StagePill label={file.status} tone='done' />
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {activeTab === 'signoff' ? (
        <Card className='rounded-[28px] border border-slate-200 shadow-none'>
          <CardHeader className='pb-4'>
            <div className='flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between'>
              <div>
                <CardTitle className='text-[1.4rem] text-slate-900'>Signoff & delivery for {task.name}</CardTitle>
                <p className='mt-2 text-sm leading-6 text-slate-500'>
                  {signoff?.message ?? 'A task-specific closing view that packages proof and approvals for this design only.'}
                </p>
              </div>
              <StagePill label={signoff?.stateLabel ?? 'Pending'} tone='review' />
            </div>
          </CardHeader>
          <CardContent className='grid gap-4 xl:grid-cols-2'>
            {(signoff?.checklist ?? []).map((item) => (
              <ChecklistCard
                key={item.id}
                icon={
                  item.done ? (
                    <CheckCircle2 className='h-5 w-5 text-emerald-500' />
                  ) : (
                    <Clock3 className='h-5 w-5 text-amber-500' />
                  )
                }
                title={item.label}
                detail={item.detail}
              />
            ))}
            {(signoff?.checklist?.length ?? 0) === 0 ? (
              <ChecklistCard
                icon={<PackageCheck className='h-5 w-5 text-[#6d5dfc]' />}
                title='Signoff not started'
                detail='The signoff checklist is generated once verification and implementation complete.'
              />
            ) : null}
            {signoff && signoff.packageContents.length ? (
              <div className='rounded-[24px] border border-slate-200 p-5 xl:col-span-2'>
                <div className='flex items-center gap-2'>
                  <ListChecks className='h-5 w-5 text-[#2563eb]' />
                  <p className='font-semibold text-slate-900'>Handoff package contents</p>
                </div>
                <ul className='mt-3 space-y-1.5 text-sm leading-6 text-slate-500'>
                  {signoff.packageContents.map((entry) => (
                    <li key={entry}>• {entry}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </section>
  )
}

function ControlButton({
  icon: Icon,
  label,
  onClick,
  tone = 'neutral',
}: {
  icon: ComponentType<{ className?: string }>
  label: string
  onClick: () => void
  tone?: 'neutral' | 'primary' | 'danger'
}) {
  const styles =
    tone === 'primary'
      ? 'bg-[#2563eb] text-white hover:bg-[#1d4ed8]'
      : tone === 'danger'
        ? 'bg-[#fdecec] text-[#d4495a] hover:bg-[#fbdcdc]'
        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'

  return (
    <button
      type='button'
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-semibold transition ${styles}`}
    >
      <Icon className='h-4 w-4' />
      {label}
    </button>
  )
}

function DetailRouteTab({
  to,
  label,
  icon,
  active,
}: {
  to: string
  label: string
  icon: string
  active: boolean
}) {
  return (
    <NavLink
      to={to}
      className={`flex items-center justify-center gap-2 rounded-[18px] px-4 py-3 text-sm font-semibold transition ${
        active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      <MaterialIcon name={icon} className='text-[18px]' />
      {label}
    </NavLink>
  )
}
