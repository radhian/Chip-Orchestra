import { NavLink } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Clock3, FileCode2, ListChecks, PackageCheck } from 'lucide-react'

import type { ArtifactItem, DiagnosisItem, RunbookEvent, SignoffStatus, TaskDetail, WorkspaceFileSummary } from '@/types/chipflow'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ChecklistCard, MaterialIcon, MiniPanel, StagePill } from '@/components/app/PlatformTaskPrimitives'

const stageCards = [
  { label: 'Spec', detail: 'Interfaces parsed', state: 'done' },
  { label: 'RTL', detail: 'Rev 4 accepted', state: 'done' },
  { label: 'TB', detail: '132 tests', state: 'done' },
  { label: 'Sim', detail: 'All pass', state: 'done' },
  { label: 'Lint', detail: '3 waivers', state: 'done' },
  { label: 'Synth', detail: 'WNS improving', state: 'active' },
  { label: 'PnR', detail: 'Queued', state: 'queued' },
  { label: 'Signoff', detail: 'Awaiting gate', state: 'queued' },
] as const

const metrics = [
  { label: 'Simulation pass set', value: 97, marker: '128/132', tone: 'bg-[#2563eb]' },
  { label: 'Functional coverage', value: 91, marker: '91%', tone: 'bg-[#3b82f6]' },
  { label: 'Lint cleanliness', value: 96, marker: '96%', tone: 'bg-[#0ea5e9]' },
] as const

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
}) {
  const primaryDiagnosis = diagnoses[0]
  const attemptLabel = task.attempts[0]?.id?.replace('attempt-', 'Attempt #') ?? 'Attempt #1'

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
            <div className='flex flex-wrap items-center gap-2'>
              <StagePill label={task.statusLabel} tone='running' />
              <StagePill label={attemptLabel} tone='neutral' />
              <StagePill label='Manual review before signoff' tone='review' />
            </div>
          </div>

          <div className='grid gap-3 xl:grid-cols-8'>
            {stageCards.map((stage) => (
              <div
                key={stage.label}
                className={`rounded-[22px] border px-4 py-5 text-center ${
                  stage.state === 'active' ? 'border-[#cbd5ff] bg-[#eef2ff]' : 'border-slate-200 bg-white'
                }`}
              >
                <p className='text-sm font-semibold text-slate-800'>{stage.label}</p>
                <p className='mt-2 text-xs text-slate-500'>{stage.detail}</p>
                <div className='mt-4 flex justify-center'>
                  <StagePill
                    label={stage.state === 'done' ? 'Done' : stage.state === 'active' ? 'Active' : 'Queued'}
                    tone={stage.state === 'done' ? 'done' : stage.state === 'active' ? 'running' : 'neutral'}
                  />
                </div>
              </div>
            ))}
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
          <MiniPanel title='Execution log' subtitle='Stage-aware logs instead of a single opaque terminal' badge='Synthesis'>
            {events.slice(0, 3).map((event) => (
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

          <MiniPanel title='AI diagnosis' subtitle='Suggested next actions stay explainable' badge='3 recommendations'>
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
                  Confidence: {primaryDiagnosis.confidence}
                </div>
              </div>
            ) : null}
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
              {metrics.map((metric) => (
                <div key={metric.label}>
                  <div className='mb-2 flex items-center justify-between gap-3'>
                    <p className='text-sm font-medium text-slate-600'>{metric.label}</p>
                    <span className='text-sm font-semibold text-slate-500'>{metric.marker}</span>
                  </div>
                  <Progress value={metric.value} indicatorClassName={metric.tone} className='h-2.5 bg-slate-100' />
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
                <p className='mt-2 text-sm leading-6 text-slate-500'>A task-specific closing view that packages proof and approvals for this design only.</p>
              </div>
              <StagePill label='Tapeout package candidate' tone='review' />
            </div>
          </CardHeader>
          <CardContent className='grid gap-4 xl:grid-cols-2'>
            <ChecklistCard
              icon={<CheckCircle2 className='h-5 w-5 text-emerald-500' />}
              title='Verification baseline frozen'
              detail='Regression snapshot, failing test history, and coverage explanations are attached to the package.'
            />
            <ChecklistCard
              icon={<ListChecks className='h-5 w-5 text-[#2563eb]' />}
              title='Implementation reports normalized'
              detail='STA, area, congestion, antenna, DRC, and LVS results are shown in one comparable schema across runs.'
            />
            <ChecklistCard
              icon={<Clock3 className='h-5 w-5 text-amber-500' />}
              title='Waiver review pending'
              detail='Two low-severity violations remain; assign owner, rationale, and expiration before export is allowed.'
            />
            <ChecklistCard
              icon={<PackageCheck className='h-5 w-5 text-[#6d5dfc]' />}
              title='One-click handoff bundle'
              detail={signoff?.message ?? 'Export GDS, netlist, liberty views, constraints, reports, and design note generated from task history.'}
            />
          </CardContent>
        </Card>
      ) : null}
    </section>
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
