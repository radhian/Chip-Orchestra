import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Bot, CircuitBoard, Cpu, FolderGit2, Layers3, Link2, PackageCheck, PlayCircle, ShieldCheck, Sparkles } from 'lucide-react'

import { createTask } from '@/api/tasks'
import { Field, SummaryRow } from '@/components/app/shared'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { CreateTaskInput } from '@/types/orchestra'

const pdkOptions = [
  { value: 'sky130', pdkId: 'sky130', stdcellLibId: 'sky130_fd_sc_hd', label: 'sky130 / sky130_fd_sc_hd' },
  { value: 'gf180mcu', pdkId: 'gf180mcu', stdcellLibId: 'gf180mcu_fd_sc_mcu7t5v0', label: 'gf180mcu / gf180mcu_fd_sc_mcu7t5v0' },
] as const

const defaultPdkOption = pdkOptions[0]

const initialForm = {
  taskName: '',
  repoSource: '',
  description: '',
  designBrief: '',
  launchMode: 'FULL_FLOW_GATED' as const,
  repoMode: 'EXISTING' as const,
  repoBranch: 'main',
  templateId: '',
  pdkId: defaultPdkOption.pdkId as string,
  stdcellLibId: defaultPdkOption.stdcellLibId as string,
  pdkLabel: defaultPdkOption.label as string,
  reviewGates: ['BEFORE_SIGNOFF'] as const,
  reviewGateLabel: 'Human approval required before signoff package',
  agentPolicy: {
    autonomy_level: 'BALANCED' as const,
    retry_budget: 2,
    auto_apply_patches: true,
  },
}

const stepCards = [
  { icon: Layers3, title: 'Choose scope', detail: 'Define the task, design goal, and review boundary.', status: 'Step 1' },
  { icon: FolderGit2, title: 'Connect source / repo', detail: 'Point the task at a repository or starter template.', status: 'Step 2' },
  { icon: Cpu, title: 'Pick environment', detail: 'Select PDK and standard-cell library defaults.', status: 'Step 3' },
  { icon: Bot, title: 'Set agent policy', detail: 'Keep a human gate before signoff while automation handles execution.', status: 'Step 4' },
]

export function CreateTaskPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const readiness = useMemo(() => {
    const required = [form.taskName, form.repoSource, form.designBrief]
    const completed = required.filter((value) => value.trim().length > 0).length
    return Math.round((completed / required.length) * 100)
  }, [form.designBrief, form.repoSource, form.taskName])

  async function handleSubmit() {
    const payload: CreateTaskInput = {
      task: {
        name: form.taskName.trim(),
        description: form.description.trim(),
        launch_mode: form.launchMode,
        design_brief: form.designBrief.trim(),
        repo_id: form.repoSource.trim(),
        repo_branch: form.repoBranch.trim(),
        repo_mode: form.repoMode,
        template_id: form.templateId.trim() || undefined,
        pdk_id: form.pdkId,
        stdcell_lib_id: form.stdcellLibId,
        review_gates: [...form.reviewGates],
        agent_policy: { ...form.agentPolicy },
      },
    }

    setSubmitting(true)
    setError(null)

    try {
      const task = await createTask(payload)
      navigate(`/tasks/${task.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task')
    } finally {
      setSubmitting(false)
    }
  }

  function handlePdkChange(value: string) {
    const selected = pdkOptions.find((o) => o.value === value) ?? defaultPdkOption
    setForm((current) => ({ ...current, pdkId: selected.pdkId, stdcellLibId: selected.stdcellLibId, pdkLabel: selected.label }))
  }

  const sourceSummary = form.repoSource.trim() || 'Repository will be attached after you enter one.'

  return (
    <div className='space-y-6'>
      <div className='flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between'>
        <div>
          <h3 className='text-2xl font-semibold text-slate-900'>Create design task</h3>
          <p className='mt-1 text-sm text-slate-500'>Submit a real Orchestrator Service task. The form posts directly to POST /api/v1/tasks.</p>
        </div>
        <div className='flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700'>
          <Sparkles className='h-4 w-4' />
          Live task submission enabled
        </div>
      </div>

      <div className='grid gap-4 xl:grid-cols-4'>
        {stepCards.map((step, index) => {
          const Icon = step.icon
          return (
            <div key={step.title} className='flex items-center gap-3'>
              <Card className='flex-1 rounded-3xl border-slate-200 shadow-none'>
                <CardContent className='flex items-start gap-4 p-4'>
                  <div className='flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700'>
                    <Icon className='h-5 w-5' />
                  </div>
                  <div>
                    <p className='text-xs font-semibold uppercase tracking-widest text-slate-400'>{step.status}</p>
                    <p className='mt-1 text-base font-semibold text-slate-900'>{step.title}</p>
                    <p className='mt-2 text-sm leading-6 text-slate-500'>{step.detail}</p>
                  </div>
                </CardContent>
              </Card>
              {index < stepCards.length - 1 ? <ArrowRight className='hidden h-5 w-5 text-slate-300 xl:block' /> : null}
            </div>
          )
        })}
      </div>

      <div className='grid gap-5 xl:grid-cols-2'>
        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <CardTitle className='text-xl'>Task configuration</CardTitle>
            <CardDescription>Set the task name, design brief, and live source of truth.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-5'>
            <div className='grid gap-5 md:grid-cols-2'>
              <Field label='Task name' hint='Human-readable and shareable across the design team'>
                <Input
                  value={form.taskName}
                  onChange={(event) => setForm((current) => ({ ...current, taskName: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                  placeholder='FFT accelerator signoff push'
                />
              </Field>
              <Field label='Repository or template' hint='Git URL, monorepo path, or source repository id'>
                <Input
                  value={form.repoSource}
                  onChange={(event) => setForm((current) => ({ ...current, repoSource: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                  placeholder='github.com/org/repo or internal repo id'
                />
              </Field>
            </div>

            <div className='grid gap-5 md:grid-cols-2'>
              <Field label='Description' hint='Optional short summary shown in the task list'>
                <Input
                  value={form.description}
                  onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                  placeholder='Short summary for the task list'
                />
              </Field>
              <Field label='Repository branch' hint='Used when creating the task in existing repo mode'>
                <Input
                  value={form.repoBranch}
                  onChange={(event) => setForm((current) => ({ ...current, repoBranch: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                  placeholder='main'
                />
              </Field>
            </div>

            <div className='grid gap-5 md:grid-cols-2'>
              <Field label='PDK / library' hint='Defaults are passed through to the Orchestrator Service'>
                <Select value={form.pdkId} onValueChange={handlePdkChange}>
                  <SelectTrigger className='h-12 rounded-2xl border-slate-200 bg-white px-4 text-sm text-slate-700 shadow-none'>
                    <SelectValue placeholder='Select PDK and library' />
                  </SelectTrigger>
                  <SelectContent>
                    {pdkOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label='Review gate' hint='This task keeps a human approval checkpoint before signoff'>
                <div className='flex h-12 items-center rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700'>{form.reviewGateLabel}</div>
              </Field>
            </div>

            <Field label='Design brief' hint='Describe the functional goal, constraints, and preferred verification behavior'>
              <Textarea
                className='min-h-40 rounded-3xl border-slate-200'
                value={form.designBrief}
                onChange={(event) => setForm((current) => ({ ...current, designBrief: event.target.value }))}
                placeholder='Describe the intended design, verification scope, and expected outputs.'
              />
            </Field>

            {error ? <p className='rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700'>{error}</p> : null}

            <div className='grid gap-5 lg:grid-cols-3'>
              <InfoCard icon={Link2} tone='blue' title='Connected source' detail='Repository and branch settings are submitted exactly as entered.' />
              <InfoCard icon={CircuitBoard} tone='emerald' title='Environment defaults' detail='PDK and library selections are sent with the task payload.' />
              <InfoCard icon={Bot} tone='violet' title='Agent policy' detail='Balanced autonomy plus retry budget is included in the live request.' />
            </div>
          </CardContent>
        </Card>

        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <CardTitle className='text-xl'>Launch preview</CardTitle>
            <CardDescription>Summary of the live payload that will be sent when you submit.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-5'>
            <div className='rounded-3xl bg-slate-50 p-4'>
              <div className='flex items-center justify-between'>
                <div>
                  <p className='text-xs uppercase tracking-widest text-slate-400'>Task readiness</p>
                  <p className='mt-2 text-3xl font-semibold text-slate-900'>{readiness}%</p>
                </div>
                <div className='flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white'>
                  <PlayCircle className='h-5 w-5' />
                </div>
              </div>
              <Progress value={readiness} className='mt-4 h-2 bg-blue-100' />
            </div>

            <div className='space-y-3 rounded-3xl border border-slate-200 p-4'>
              <SummaryRow icon={Cpu} title='Launch mode' value={form.launchMode} />
              <SummaryRow icon={FolderGit2} title='Source' value={sourceSummary} />
              <SummaryRow icon={ShieldCheck} title='Review policy' value={form.reviewGateLabel} />
              <SummaryRow icon={PackageCheck} title='Artifacts' value='Artifacts will be generated by the backend and attached to the task over time.' />
            </div>

            <Button
              disabled={submitting || readiness < 100}
              onClick={handleSubmit}
              className='h-12 w-full rounded-2xl bg-blue-600 text-base hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300'
            >
              {submitting ? 'Creating task…' : 'Create task'}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function InfoCard({
  icon: Icon,
  tone,
  title,
  detail,
}: {
  icon: typeof Bot
  tone: 'blue' | 'emerald' | 'violet'
  title: string
  detail: string
}) {
  const toneMap = {
    blue: 'border-blue-100 bg-blue-50 text-blue-700',
    emerald: 'border-emerald-100 bg-emerald-50 text-emerald-700',
    violet: 'border-violet-100 bg-violet-50 text-violet-700',
  } as const

  return (
    <Card className={`rounded-2xl border shadow-none ${toneMap[tone]}`}>
      <CardContent className='space-y-2 p-4'>
        <div className='flex items-center gap-2'>
          <Icon className='h-4 w-4' />
          <p className='font-semibold'>{title}</p>
        </div>
        <p className='text-sm leading-6 opacity-90'>{detail}</p>
      </CardContent>
    </Card>
  )
}
