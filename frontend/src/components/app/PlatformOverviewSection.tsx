import type { TaskFilter, TaskSummary, WorkflowStep } from '@/types/chiporchestra'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const filterItems: { key: TaskFilter; label: string }[] = [
  { key: 'all', label: 'All repos' },
  { key: 'mine', label: 'My tasks' },
  { key: 'review', label: 'Needs review' },
  { key: 'failed', label: 'Failed' },
]

function MaterialIcon({ name, className = '' }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden='true'>{name}</span>
}

export function PlatformOverviewSection({
  activeFilter,
  selectedTaskId,
  tasks,
  workflowSteps,
  onFilterChange,
  onSelectTask,
}: {
  activeFilter: TaskFilter
  selectedTaskId: string
  tasks: TaskSummary[]
  workflowSteps: WorkflowStep[]
  onFilterChange: (filter: TaskFilter) => void
  onSelectTask: (taskId: string) => void
}) {
  return (
    <section id='overview' className='space-y-5 scroll-mt-24'>
      <div className='flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between'>
        <div>
          <h3 className='text-[2rem] font-semibold tracking-tight text-slate-900'>Task dashboard</h3>
          <p className='mt-1 text-sm leading-6 text-slate-500'>
            A lean MVP home focused on active design tasks, status, and the path from RTL to GDS.
          </p>
        </div>

        <div className='flex flex-wrap gap-2'>
          {filterItems.map((filter) => {
            const active = filter.key === activeFilter

            return (
              <Button
                key={filter.key}
                type='button'
                variant='outline'
                onClick={() => onFilterChange(filter.key)}
                className={`h-10 rounded-full border px-4 text-sm ${
                  active
                    ? 'border-[#2563eb] bg-[#2563eb] text-white hover:bg-[#2563eb] hover:text-white'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                {filter.label}
              </Button>
            )
          })}
        </div>
      </div>

      <Card className='overflow-hidden rounded-[28px] border border-slate-200 bg-[#f8fafc] shadow-none'>
        <CardContent className='p-0'>
          <div className='grid grid-cols-[2.2fr_1fr_1.2fr_.8fr_.8fr] gap-3 border-b border-slate-200 px-6 py-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400'>
            <span>Task</span>
            <span>Owner</span>
            <span>Current stage</span>
            <span>ETA</span>
            <span>Status</span>
          </div>

          <div className='divide-y divide-slate-200'>
            {tasks.map((task) => {
              const active = task.id === selectedTaskId

              return (
                <button
                  key={task.id}
                  type='button'
                  onClick={() => onSelectTask(task.id)}
                  className={`grid w-full grid-cols-[2.2fr_1fr_1.2fr_.8fr_.8fr] gap-3 px-6 py-4 text-left transition ${
                    active ? 'bg-[#eef2ff]' : 'bg-transparent hover:bg-white'
                  }`}
                >
                  <div>
                    <p className='font-semibold text-slate-900'>{task.name}</p>
                    <p className='mt-1 text-sm text-slate-500'>{task.repoName}</p>
                  </div>
                  <div className='text-sm text-slate-600'>{task.ownerName}</div>
                  <div className='text-sm text-slate-600'>{task.currentStage}</div>
                  <div className='text-sm text-slate-600'>{task.etaLabel}</div>
                  <div>
                    <StatusBadge tone={task.tone} label={task.statusLabel} />
                  </div>
                </button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      <Card className='rounded-[28px] border border-slate-200 shadow-none'>
        <CardHeader className='flex flex-row items-start justify-between gap-3'>
          <div>
            <CardTitle className='text-[1.4rem] text-slate-900'>RTL-to-GDS workflow</CardTitle>
            <p className='mt-2 text-sm leading-6 text-slate-500'>
              A simple stage map for the MVP flow, from specification input to signoff packaging.
            </p>
          </div>
          <Badge className='rounded-full border-0 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500 hover:bg-slate-100'>
            MVP flow
          </Badge>
        </CardHeader>
        <CardContent>
          <div className='grid gap-4 xl:grid-cols-5'>
            {workflowSteps.map((step) => (
              <Card key={step.title} className='rounded-[24px] border border-slate-200 shadow-none'>
                <CardContent className='space-y-4 p-5'>
                  <div className={`flex h-11 w-11 items-center justify-center rounded-full ${toneMap[step.tone]}`}>
                    <MaterialIcon name={step.label} className='text-[18px]' />
                  </div>
                  <div>
                    <p className='text-lg font-semibold text-slate-900'>{step.title}</p>
                    <p className='mt-2 text-sm leading-6 text-slate-500'>{step.detail}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

const toneMap = {
  violet: 'bg-[#efe9ff] text-[#6d5dfc]',
  mint: 'bg-[#e7fbf4] text-[#11a88a]',
  sky: 'bg-[#e8f4ff] text-[#2563eb]',
  amber: 'bg-[#fff2dd] text-[#f59e0b]',
  rose: 'bg-[#ffe8ed] text-[#ef476f]',
} as const

function StatusBadge({ tone, label }: { tone: TaskSummary['tone']; label: string }) {
  const className =
    tone === 'running'
      ? 'bg-[#ecebff] text-[#5b5bd6]'
      : tone === 'review'
        ? 'bg-[#fff3df] text-[#c77a00]'
        : tone === 'passed'
          ? 'bg-[#e7fbf4] text-[#139d82]'
          : 'bg-[#ffe8ed] text-[#d64565]'

  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${className}`}>{label}</span>
}
