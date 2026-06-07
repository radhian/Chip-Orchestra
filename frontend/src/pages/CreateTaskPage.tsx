import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Bot,
  CircuitBoard,
  Cpu,
  FlaskConical,
  FolderGit2,
  Layers3,
  Link2,
  PackageCheck,
  PlayCircle,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

import { createTask } from '@/api/tasks'
import { Field, SummaryRow } from '@/components/app/shared'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import type { CreateTaskInput } from '@/types/chiporchestra'

const defaultForm = {
  taskName: 'FFT Accelerator 1024p signoff push',
  repoSource: 'github.com/chiporchestra/fft-accelerator-demo',
  designBrief:
    'Build a compact FFT accelerator flow that can ingest a prior RTL baseline, run lint and simulation, recover common timing regressions, and produce a signoff-ready package with explicit artifact lineage.',
  launchMode: 'FULL_FLOW_GATED' as const,
  repoMode: 'EXISTING' as const,
  repoBranch: 'main',
  templateId: 'digital-block-starter',
  pdkId: 'sky130',
  stdcellLibId: 'gf180-mixed-eval',
  pdkLabel: 'Sky130 / GF180 mixed evaluation stack',
  reviewGates: ['BEFORE_SIGNOFF'] as const,
  reviewGateLabel: 'Human approval required before signoff package',
  agentPolicy: {
    autonomy_level: 'BALANCED' as const,
    retry_budget: 2,
    auto_apply_patches: true,
  },
}

const stepCards = [
  {
    icon: Layers3,
    title: 'Choose scope',
    detail: 'Start from a reusable design object, IP template, or repo branch.',
    status: 'Step 1',
  },
  {
    icon: FolderGit2,
    title: 'Connect source / repo',
    detail: 'Attach Git repo, upload a brief, or select from a design starter kit.',
    status: 'Step 2',
  },
  {
    icon: Cpu,
    title: 'Pick environment',
    detail: 'Select PDK, libraries, runtime image, and verification presets.',
    status: 'Step 3',
  },
  {
    icon: Bot,
    title: 'Set agent policy',
    detail: 'Define autonomy, review gate, escalation path, and artifact expectations.',
    status: 'Step 4',
  },
]

export function CreateTaskPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(defaultForm)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    const payload: CreateTaskInput = {
      task: {
        name: form.taskName,
        launch_mode: form.launchMode,
        design_brief: form.designBrief,
        repo_id: form.repoSource,
        repo_branch: form.repoBranch,
        repo_mode: form.repoMode,
        template_id: form.templateId,
        pdk_id: form.pdkId,
        stdcell_lib_id: form.stdcellLibId,
        review_gates: [...form.reviewGates],
        agent_policy: { ...form.agentPolicy },
      },
    }

    setSubmitting(true)
    try {
      const task = await createTask(payload)
      navigate(`/tasks/${task.id}`)
    } finally {
      setSubmitting(false)
    }
  }

  const sourceSummary =
    form.repoSource === defaultForm.repoSource ? 'FFT accelerator demo repo and markdown brief' : form.repoSource

  return (
    <div className='space-y-6'>
      <div className='flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between'>
        <div>
          <h3 className='text-2xl font-semibold text-slate-900'>Create design task</h3>
          <p className='mt-1 text-sm text-slate-500'>
            A four-step setup flow that keeps RTL, environment selection, and review policy in one place.
          </p>
        </div>
        <div className='flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700'>
          <Sparkles className='h-4 w-4' />
          Agent draft mode enabled
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
            <CardDescription>Set the task name, design brief, and source of truth.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-5'>
            <div className='grid gap-5 md:grid-cols-2'>
              <Field label='Task name' hint='Human-readable and sharable across the design team'>
                <Input
                  value={form.taskName}
                  onChange={(event) => setForm((current) => ({ ...current, taskName: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                />
              </Field>
              <Field label='Repository or template' hint='Git URL, monorepo path, or starter design object'>
                <Input
                  value={form.repoSource}
                  onChange={(event) => setForm((current) => ({ ...current, repoSource: event.target.value }))}
                  className='h-12 rounded-2xl border-slate-200'
                />
              </Field>
            </div>

            <div className='grid gap-5 md:grid-cols-2'>
              <Field label='PDK / library' hint='Select the environment used for synthesis and signoff'>
                <div className='flex h-12 items-center rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700'>
                  {form.pdkLabel}
                </div>
              </Field>
              <Field label='Review gate' hint='Decide how much autonomy agents receive before escalation'>
                <div className='flex h-12 items-center rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700'>
                  {form.reviewGateLabel}
                </div>
              </Field>
            </div>

            <Field label='Design brief' hint='Describe the functional goal, constraints, and preferred verification behavior'>
              <Textarea
                className='min-h-40 rounded-3xl border-slate-200'
                value={form.designBrief}
                onChange={(event) => setForm((current) => ({ ...current, designBrief: event.target.value }))}
              />
            </Field>

            <div className='grid gap-5 lg:grid-cols-3'>
              <InfoCard
                icon={Link2}
                tone='blue'
                title='Connected source'
                detail='Repo context, markdown spec, and artifact cache are attached as design inputs.'
              />
              <InfoCard
                icon={FlaskConical}
                tone='emerald'
                title='Verification preset'
                detail='Smoke regressions, lint checks, and waveform checkpoints enabled by default.'
              />
              <InfoCard
                icon={Bot}
                tone='violet'
                title='Agent policy'
                detail='Auto-diagnose failures, suggest fixes, and wait at the final review gate.'
              />
            </div>
          </CardContent>
        </Card>

        <Card className='rounded-3xl border-slate-200 shadow-none'>
          <CardHeader>
            <CardTitle className='text-xl'>Launch preview</CardTitle>
            <CardDescription>Summary of what this task will create when submitted.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-5'>
            <div className='rounded-3xl bg-slate-50 p-4'>
              <div className='flex items-center justify-between'>
                <div>
                  <p className='text-xs uppercase tracking-widest text-slate-400'>Task readiness</p>
                  <p className='mt-2 text-3xl font-semibold text-slate-900'>92%</p>
                </div>
                <div className='flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white'>
                  <PlayCircle className='h-5 w-5' />
                </div>
              </div>
              <Progress value={92} className='mt-4 h-2 bg-blue-100' />
            </div>

            <div className='space-y-3 rounded-3xl border border-slate-200 p-4'>
              <SummaryRow icon={CircuitBoard} title='Runtime' value='EDA pod with synthesis + verification queue' />
              <SummaryRow icon={FolderGit2} title='Source' value={sourceSummary} />
              <SummaryRow icon={ShieldCheck} title='Review policy' value='Human gate before signoff and delivery' />
              <SummaryRow icon={PackageCheck} title='Artifacts' value='RTL diff, waveform report, timing snapshot, handoff bundle' />
            </div>

            <Button disabled={submitting} onClick={handleSubmit} className='h-12 w-full rounded-2xl bg-blue-600 text-base hover:bg-blue-700'>
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
