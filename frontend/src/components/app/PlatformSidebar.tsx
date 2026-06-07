import { NavLink } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type SidebarSection = 'overview' | 'create' | 'detail'

const navItems: { key: SidebarSection; label: string; icon: string; href: string }[] = [
  { key: 'overview', label: 'Overview Console', icon: 'space_dashboard', href: '/overview' },
  { key: 'create', label: 'Create Design Task', icon: 'add_circle', href: '/tasks/new' },
  { key: 'detail', label: 'Task Detail & Runbook', icon: 'manufacturing', href: '/tasks/fft-1024p' },
]

function MaterialIcon({ name, className = '' }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden='true'>{name}</span>
}

export function PlatformSidebar({
  activeSection,
  detailHref,
}: {
  activeSection: SidebarSection
  detailHref?: string
}) {
  return (
    <aside className='flex w-full flex-col gap-4 rounded-[28px] bg-white/95 p-4 shadow-[0_24px_80px_rgba(148,163,184,0.18)] backdrop-blur xl:sticky xl:top-4 xl:w-[284px] xl:self-start'>
      <div className='rounded-[26px] bg-slate-50 p-4'>
        <div className='flex items-start justify-between gap-3'>
          <div>
            <p className='text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400'>AI-native chip design</p>
            <h1 className='mt-2 text-[2rem] font-semibold tracking-tight text-[#2563eb]'>ChipFlowAI</h1>
          </div>
          <div className='flex h-14 w-14 items-center justify-center rounded-[18px] bg-gradient-to-br from-[#4f7cff] via-[#3ea6ff] to-[#2dd4bf] text-white shadow-lg shadow-cyan-200/70'>
            <MaterialIcon name='memory' className='text-[24px]' />
          </div>
        </div>

        <div className='mt-4 rounded-[24px] bg-gradient-to-br from-[#4969ff] via-[#2f83ff] to-[#18c3de] p-4 text-white shadow-[0_16px_42px_rgba(63,121,255,0.35)]'>
          <p className='text-[11px] font-semibold uppercase tracking-[0.22em] text-white/70'>Wireframe direction</p>
          <h2 className='mt-3 text-[1.75rem] font-semibold leading-8'>Task-centric UX modeled after modern AI generation consoles</h2>
          <p className='mt-4 text-sm leading-6 text-white/85'>
            List → create → run → diagnose → signoff, all surfaced in a browser-native hardware workflow.
          </p>
        </div>
      </div>

      <div className='rounded-[24px] bg-slate-50 p-3'>
        {navItems.map((item) => {
          const active = item.key === activeSection
          const href = item.key === 'detail' ? detailHref ?? '/tasks/fft-1024p' : item.href

          return (
            <NavLink
              key={item.key}
              to={href}
              className={`mb-2 flex w-full items-center rounded-[18px] px-3 py-3 text-left transition-all last:mb-0 ${
                active
                  ? 'bg-white text-slate-900 shadow-[0_10px_30px_rgba(148,163,184,0.22)] ring-1 ring-[#c9d6ee]'
                  : 'text-slate-500 hover:bg-white/80 hover:text-slate-800'
              }`}
            >
              <div className='flex items-center gap-3'>
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-[14px] ${
                    active ? 'bg-[#e7f0ff] text-[#2563eb]' : 'bg-slate-200 text-slate-500'
                  }`}
                >
                  <MaterialIcon name={item.icon} className='text-[18px]' />
                </div>
                <div className='text-sm font-semibold'>{item.label}</div>
              </div>
            </NavLink>
          )
        })}
      </div>

      <div className='space-y-4'>
        <Card className='rounded-[24px] border-0 bg-slate-50 shadow-none'>
          <CardContent className='space-y-4 p-4'>
            <div className='flex items-center justify-between gap-3'>
              <div>
                <p className='text-xs font-semibold text-slate-500'>Repository context</p>
                <p className='text-xs text-slate-400'>single source of design truth</p>
              </div>
              <Badge className='rounded-full border-0 bg-[#eef2ff] px-3 py-1 text-[11px] font-semibold text-[#5b5bd6] hover:bg-[#eef2ff]'>
                RAG enabled
              </Badge>
            </div>

            <div className='grid gap-3 text-sm'>
              <InfoCell label='Repo' value='chipflowai/digital-demo' />
              <div className='grid grid-cols-2 gap-3'>
                <InfoCell label='PDK' value='Sky130 / GF180' />
                <InfoCell label='Runtime' value='Agent + EDA pods' />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className='rounded-[24px] border-0 bg-slate-50 shadow-none'>
          <CardHeader className='pb-3'>
            <CardTitle className='text-sm text-slate-700'>Primary UX principles</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3 pt-0 text-sm leading-6 text-slate-600'>
            <Principle icon='smart_toy' text='Task-first orchestration instead of tool-first navigation' tone='text-[#2563eb]' />
            <Principle icon='verified' text='AI suggestions remain inspectable, rerunnable, and auditable' tone='text-[#0f9f8b]' />
            <Principle icon='inventory_2' text='Every stage emits artifacts, metrics, and next actions' tone='text-[#6d5dfc]' />
          </CardContent>
        </Card>
      </div>
    </aside>
  )
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className='text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400'>{label}</p>
      <p className='mt-1 text-sm font-semibold text-slate-900'>{value}</p>
    </div>
  )
}

function Principle({ icon, text, tone }: { icon: string; text: string; tone: string }) {
  return (
    <div className='flex gap-2'>
      <MaterialIcon name={icon} className={`mt-0.5 text-[18px] ${tone}`} />
      <p>{text}</p>
    </div>
  )
}
