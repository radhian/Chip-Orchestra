import { ArrowRight, Bot, Cpu, FolderGit2, Layers3, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import type { ResearchDepth } from '@/types/chiporchestra'

export type LaunchForm = {
  taskName: string
  launchMode: string
  designBrief: string
  pdk: string
  reviewGate: string
  clockPeriodNs: string
  researchDepth: ResearchDepth
}

export const researchDepthLevels: ResearchDepth[] = ['SMALL', 'MEDIUM', 'DEEP']
export const researchDepthMeta: Record<ResearchDepth, { label: string; detail: string }> = {
  SMALL: { label: 'Small', detail: '3 GitHub + 3 web — fastest, lighter grounding.' },
  MEDIUM: { label: 'Medium', detail: '6 GitHub + 6 web — balanced (default).' },
  DEEP: { label: 'Deep', detail: '10 GitHub + 10 web — most references, slowest.' },
}

export const launchModeOptions = [
  { value: 'FULL_FLOW_GATED', label: 'Full flow with gated approvals' },
  { value: 'GEN_ONLY', label: 'RTL generation only' },
  { value: 'VERIFY_RESCUE', label: 'Verification rescue' },
  { value: 'SYNTH_ONLY', label: 'Synthesis / hardening only' },
]

export const pdkOptions = [
  { value: 'sky130', label: 'Sky130 HD (sky130_fd_sc_hd)' },
  { value: 'gf180', label: 'GF180MCU (gf180mcu_fd_sc_mcu7t5v0)' },
]

export const reviewGateOptions = [
  { value: 'BOTH', label: 'Before synthesis and before signoff' },
  { value: 'BEFORE_SYNTH', label: 'Before synthesis only' },
  { value: 'BEFORE_SIGNOFF', label: 'Before signoff only' },
]

const steps = [
  {
    number: '1',
    title: 'Choose scope',
    detail: 'RTL generation, verification rescue, synthesis closure, or full RTL-to-GDS flow.',
    icon: Layers3,
  },
  {
    number: '2',
    title: 'Describe the block',
    detail: 'A natural-language design brief is the prompt that drives the agentic RTL pipeline.',
    icon: FolderGit2,
  },
  {
    number: '3',
    title: 'Pick environment',
    detail: 'PDK, standard-cell library, target clock, and review gates are explicit task parameters.',
    icon: Cpu,
  },
  {
    number: '4',
    title: 'Launch agent',
    detail: 'LangGraph agents plan, generate, simulate, self-correct, and harden — all observable.',
    icon: Bot,
  },
]

const fieldShell =
  'mt-2 w-full rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 outline-none transition focus:border-[#2563eb] focus:ring-2 focus:ring-[#2563eb]/15'

export function PlatformCreateSection({
  form,
  creating,
  onChange,
  onSubmit,
}: {
  form: LaunchForm
  creating: boolean
  onChange: (patch: Partial<LaunchForm>) => void
  onSubmit: () => void
}) {
  const canSubmit = form.taskName.trim().length > 0 && form.designBrief.trim().length > 0

  return (
    <section id='create' className='space-y-5 scroll-mt-24'>
      <div className='flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between'>
        <div>
          <h3 className='text-[2rem] font-semibold tracking-tight text-slate-900'>Create design task</h3>
          <p className='mt-1 text-sm leading-6 text-slate-500'>
            Describe the hardware block in plain language; the agent generates, simulates, self-corrects, and hardens it.
          </p>
        </div>

        <div className='inline-flex items-center gap-2 rounded-full bg-[#eef2ff] px-4 py-2 text-sm font-semibold text-[#5b5bd6]'>
          <Sparkles className='h-4 w-4' />
          Agentic launch
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
            <FieldLabel label='Task name' className='md:col-span-2'>
              <input
                className={fieldShell}
                value={form.taskName}
                placeholder='e.g. uart_tx 8N1 controller'
                onChange={(e) => onChange({ taskName: e.target.value })}
              />
            </FieldLabel>

            <FieldLabel label='Design brief (prompt)' className='md:col-span-2'>
              <textarea
                className={`${fieldShell} min-h-[132px] resize-y`}
                value={form.designBrief}
                placeholder='Describe the block: function, interface ports, protocol, timing, and any constraints.'
                onChange={(e) => onChange({ designBrief: e.target.value })}
              />
            </FieldLabel>

            <FieldLabel label='Launch mode'>
              <select
                className={fieldShell}
                value={form.launchMode}
                onChange={(e) => onChange({ launchMode: e.target.value })}
              >
                {launchModeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <FieldLabel label='PDK / library'>
              <select className={fieldShell} value={form.pdk} onChange={(e) => onChange({ pdk: e.target.value })}>
                {pdkOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <FieldLabel label='Target clock period (ns)'>
              <input
                className={fieldShell}
                type='number'
                min='1'
                step='0.1'
                value={form.clockPeriodNs}
                onChange={(e) => onChange({ clockPeriodNs: e.target.value })}
              />
            </FieldLabel>

            <FieldLabel label='Review gate'>
              <select
                className={fieldShell}
                value={form.reviewGate}
                onChange={(e) => onChange({ reviewGate: e.target.value })}
              >
                {reviewGateOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <div className='md:col-span-2'>
              <div className='flex items-center justify-between'>
                <span className='text-sm font-semibold text-slate-900'>Research depth</span>
                <span className='text-sm font-semibold text-[#2563eb]'>
                  {researchDepthMeta[form.researchDepth].label}
                </span>
              </div>
              <div className='mt-4 px-1'>
                <Slider
                  min={0}
                  max={2}
                  step={1}
                  value={[researchDepthLevels.indexOf(form.researchDepth)]}
                  onValueChange={(v) => onChange({ researchDepth: researchDepthLevels[v[0]] })}
                />
                <div className='mt-2 flex justify-between text-xs font-medium text-slate-400'>
                  {researchDepthLevels.map((level) => (
                    <span key={level}>{researchDepthMeta[level].label}</span>
                  ))}
                </div>
              </div>
              <p className='mt-2 text-xs leading-5 text-slate-500'>
                {researchDepthMeta[form.researchDepth].detail} The agent crawls GitHub + the web for
                reference designs and RAG-ranks them into the generator.
              </p>
            </div>
          </div>

          <div className='flex flex-col justify-between rounded-[24px] bg-[#f8fafc] p-5'>
            <div>
              <p className='text-xs font-semibold uppercase tracking-[0.22em] text-slate-400'>Launch preview</p>
              <p className='mt-3 text-lg font-semibold text-slate-900'>The brief is the agent prompt.</p>
              <ul className='mt-4 space-y-3 text-sm leading-6 text-slate-600'>
                <li>• Agents plan → generate RTL → simulate → self-correct → harden.</li>
                <li>• Every step streams into the task runbook, artifacts, and diagnosis.</li>
                <li>• Review gates stay declared before synthesis and signoff.</li>
              </ul>
            </div>

            <Button
              type='button'
              onClick={onSubmit}
              disabled={creating || !canSubmit}
              className='mt-6 h-12 rounded-[18px] bg-[#2563eb] text-base font-semibold hover:bg-[#1d4ed8]'
            >
              {creating ? 'Launching agent…' : 'Launch agentic task'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}

function FieldLabel({
  label,
  children,
  className = '',
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <label className={`block ${className}`}>
      <span className='text-sm font-semibold text-slate-900'>{label}</span>
      {children}
    </label>
  )
}
