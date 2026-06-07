import { ArrowRight, Bot, Cpu, FolderGit2, Layers3, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

type LaunchForm = {
  taskName: string
  launchMode: string
  designBrief: string
  repositorySource: string
  bootstrapOption: string
  pdkLibrary: string
  reviewGate: string
}

const steps = [
  {
    number: '1',
    title: 'Choose scope',
    detail: 'RTL generation, verification rescue, synthesis closure, or full RTL-to-GDS flow.',
    icon: Layers3,
  },
  {
    number: '2',
    title: 'Connect source',
    detail: 'Link an existing repository or bootstrap a new repository from a starter template.',
    icon: FolderGit2,
  },
  {
    number: '3',
    title: 'Pick environment',
    detail: 'PDK, standard-cell library, simulator, synthesis recipe, and compute class are explicit task parameters.',
    icon: Cpu,
  },
  {
    number: '4',
    title: 'Set agent policy',
    detail: 'Select autonomy level, retry budget, review gates, and whether code patches can be applied automatically.',
    icon: Bot,
  },
]

export function PlatformCreateSection({
  form,
  creating,
  onSubmit,
}: {
  form: LaunchForm
  creating: boolean
  onSubmit: () => void
}) {
  return (
    <section id='create' className='space-y-5 scroll-mt-24'>
      <div className='flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between'>
        <div>
          <h3 className='text-[2rem] font-semibold tracking-tight text-slate-900'>Create design task</h3>
          <p className='mt-1 text-sm leading-6 text-slate-500'>
            A lean launch flow for RTL-to-GDS MVP work: pick the task type, point to a repo, and run with a standard flow.
          </p>
        </div>

        <div className='inline-flex items-center gap-2 rounded-full bg-[#eef2ff] px-4 py-2 text-sm font-semibold text-[#5b5bd6]'>
          <Sparkles className='h-4 w-4' />
          MVP launch
        </div>
      </div>

      <div className='grid gap-4 xl:grid-cols-4'>
        {steps.map((step, index) => {
          const Icon = step.icon

          return (
            <div key={step.title} className='flex items-center gap-3'>
              <Card className='flex-1 rounded-[28px] border border-slate-200 shadow-none'>
                <CardContent className='flex h-full gap-4 p-5'>
                  <div className='flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] bg-slate-100 text-slate-700'>
                    <span className='text-base font-semibold'>{step.number}</span>
                  </div>
                  <div>
                    <div className='flex items-center gap-2'>
                      <Icon className='h-4 w-4 text-slate-400' />
                      <p className='text-base font-semibold text-slate-900'>{step.title}</p>
                    </div>
                    <p className='mt-2 text-sm leading-6 text-slate-500'>{step.detail}</p>
                  </div>
                </CardContent>
              </Card>
              {index < steps.length - 1 ? <ArrowRight className='hidden h-5 w-5 text-slate-300 xl:block' /> : null}
            </div>
          )
        })}
      </div>

      <Card className='rounded-[28px] border border-slate-200 shadow-none'>
        <CardContent className='grid gap-5 p-6 xl:grid-cols-[1.2fr_.8fr]'>
          <div className='grid gap-4 md:grid-cols-2'>
            <Field label='Task name' value={form.taskName} />
            <Field label='Launch mode' value={form.launchMode} />
            <Field label='Design brief' value={form.designBrief} multiLine />
            <Field label='Repository source' value={form.repositorySource} multiLine />
            <Field label='Bootstrap option' value={form.bootstrapOption} />
            <Field label='PDK / library' value={form.pdkLibrary} />
            <Field label='Review gate' value={form.reviewGate} className='md:col-span-2' />
          </div>

          <div className='flex flex-col justify-between rounded-[24px] bg-[#f8fafc] p-5'>
            <div>
              <p className='text-xs font-semibold uppercase tracking-[0.22em] text-slate-400'>Launch preview</p>
              <p className='mt-3 text-lg font-semibold text-slate-900'>Task parameters are explicit before the run starts.</p>
              <ul className='mt-4 space-y-3 text-sm leading-6 text-slate-600'>
                <li>• Repo, template, and design brief are visible at kickoff.</li>
                <li>• Review gates are declared before synthesis and signoff.</li>
                <li>• Agent policy stays inspectable for every attempt.</li>
              </ul>
            </div>

            <Button
              type='button'
              onClick={onSubmit}
              disabled={creating}
              className='mt-6 h-12 rounded-[18px] bg-[#2563eb] text-base font-semibold hover:bg-[#1d4ed8]'
            >
              {creating ? 'Creating task…' : 'Create task'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

function Field({
  label,
  value,
  multiLine = false,
  className = '',
}: {
  label: string
  value: string
  multiLine?: boolean
  className?: string
}) {
  return (
    <div className={className}>
      <p className='text-sm font-semibold text-slate-900'>{label}</p>
      <div
        className={`mt-2 rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-600 ${
          multiLine ? 'min-h-[116px]' : 'min-h-[54px]'
        }`}
      >
        {value}
      </div>
    </div>
  )
}
