import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { Bot, LayoutGrid, PackageCheck, ShieldCheck, Sparkles, Waypoints } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const navItems: {
  key: 'overview' | 'create' | 'detail'
  label: string
  icon: typeof LayoutGrid
  to: string
  isActive: (pathname: string) => boolean
}[] = [
  {
    key: 'overview',
    label: 'Overview Console',
    icon: LayoutGrid,
    to: '/overview',
    isActive: (pathname) => pathname === '/overview',
  },
  {
    key: 'create',
    label: 'Create Design Task',
    icon: Sparkles,
    to: '/tasks/new',
    isActive: (pathname) => pathname === '/tasks/new',
  },
  {
    key: 'detail',
    label: 'Task Detail & Runbook',
    icon: Waypoints,
    to: '/tasks/fft-1024p',
    isActive: (pathname) => pathname.startsWith('/tasks/') && pathname !== '/tasks/new',
  },
]

function getDetailTarget(pathname: string) {
  if (!pathname.startsWith('/tasks/') || pathname === '/tasks/new') {
    return '/tasks/fft-1024p'
  }

  const [, , taskId] = pathname.split('/')
  return taskId ? `/tasks/${taskId}` : '/tasks/fft-1024p'
}

function MaterialIcon({ name, className = '' }: { name: string; className?: string }) {
  return <span className={`material-symbols-rounded ${className}`.trim()} aria-hidden='true'>{name}</span>
}

export function ShellLayout() {
  const { pathname } = useLocation()

  return (
    <div className='min-h-screen bg-slate-100 text-slate-800'>
      <div className='mx-auto flex min-h-screen max-w-screen-2xl gap-3 p-2 sm:gap-4 sm:p-3 lg:p-4'>
        <aside className='hidden w-72 shrink-0 rounded-3xl bg-white p-4 shadow-xl lg:flex lg:flex-col'>
          <div className='rounded-3xl bg-slate-50 p-4'>
            <div className='flex items-start justify-between gap-3'>
              <div>
                <p className='text-xs font-semibold uppercase tracking-widest text-slate-400'>AI-native chip design</p>
                <h1 className='mt-2 text-3xl font-semibold tracking-tight text-blue-600'>ChipOrchestra</h1>
              </div>
              <div className='flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 px-1 text-xs font-semibold leading-none text-white shadow-lg'>
                <MaterialIcon name='memory' className='text-[24px]' />
              </div>
            </div>

            <div className='mt-4 rounded-3xl bg-gradient-to-br from-blue-600 via-sky-500 to-cyan-400 p-4 text-white shadow-xl'>
              <p className='text-xs font-medium uppercase tracking-widest text-blue-100'>Wireframe direction</p>
              <h2 className='mt-3 text-2xl font-semibold leading-8'>Task-centric UX modeled after modern AI generation consoles</h2>
              <p className='mt-4 text-sm leading-6 text-blue-50'>
                list → create → run → diagnose → signoff, all surfaced in a browser-native hardware workflow.
              </p>
            </div>
          </div>

          <div className='mt-4 rounded-3xl bg-slate-50 p-3'>
            {navItems.map((item) => {
              const Icon = item.icon
              const active = item.isActive(pathname)
              const target = item.key === 'detail' ? getDetailTarget(pathname) : item.to

              return (
                <NavLink
                  key={item.key}
                  to={target}
                  className={`mb-2 flex w-full items-center rounded-2xl px-3 py-3 text-left transition-all ${
                    active
                      ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-500 hover:bg-white/80 hover:text-slate-800'
                  }`}
                >
                  <div className='flex items-center gap-3'>
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-xl ${
                        active ? 'bg-blue-50 text-blue-600' : 'bg-slate-200 text-slate-500'
                      }`}
                    >
                      <Icon className='h-4 w-4' />
                    </div>
                    <div>
                      <div className='whitespace-nowrap text-sm font-semibold'>{item.label}</div>
                    </div>
                  </div>
                </NavLink>
              )
            })}
          </div>

          <div className='mt-auto space-y-4'>
            <Card className='border-0 bg-slate-50 shadow-none'>
              <CardContent className='space-y-4 p-4'>
                <div className='flex items-center justify-between'>
                  <div>
                    <p className='text-xs font-semibold text-slate-500'>Repository context</p>
                    <p className='text-xs text-slate-400'>Single source of design truth</p>
                  </div>
                  <Badge className='bg-indigo-100 text-indigo-700 hover:bg-indigo-100'>RAG enabled</Badge>
                </div>
                <div className='grid grid-cols-2 gap-3 text-sm'>
                  <div>
                    <p className='text-xs uppercase tracking-wide text-slate-400'>Repo</p>
                    <p className='mt-1 font-medium'>chiporchestra/digital-demo</p>
                  </div>
                  <div>
                    <p className='text-xs uppercase tracking-wide text-slate-400'>PDK</p>
                    <p className='mt-1 font-medium'>Sky130 / GF180</p>
                  </div>
                  <div>
                    <p className='text-xs uppercase tracking-wide text-slate-400'>Runtime</p>
                    <p className='mt-1 font-medium'>Agent + EDA pods</p>
                  </div>
                  <div>
                    <p className='text-xs uppercase tracking-wide text-slate-400'>Review gate</p>
                    <p className='mt-1 font-medium'>Human + AI copilot</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className='border-0 bg-slate-50 shadow-none'>
              <CardHeader className='pb-3'>
                <CardTitle className='text-sm'>Primary UX principles</CardTitle>
              </CardHeader>
              <CardContent className='space-y-3 pt-0 text-sm text-slate-600'>
                <div className='flex gap-2'>
                  <Bot className='mt-0.5 h-4 w-4 text-blue-500' />
                  <p>Task-first orchestration, not tool-first navigation.</p>
                </div>
                <div className='flex gap-2'>
                  <ShieldCheck className='mt-0.5 h-4 w-4 text-emerald-500' />
                  <p>Every suggestion stays inspectable, rerunnable, and auditable.</p>
                </div>
                <div className='flex gap-2'>
                  <PackageCheck className='mt-0.5 h-4 w-4 text-violet-500' />
                  <p>Every step emits artifacts, metrics, and clear next actions.</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </aside>

        <main className='flex-1 space-y-4'>
          <section className='rounded-3xl bg-white px-5 py-5 shadow-xl sm:px-6'>
            <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
              <div className='max-w-3xl'>
                <p className='text-sm font-medium text-slate-400'>Product proposal companion wireframe</p>
                <h2 className='mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl'>
                 Chip Orchestra digital IC platform
                </h2>
                <p className='mt-3 max-w-3xl text-sm leading-6 text-slate-500 sm:text-base'>
                  An interactive mockup for a browser-based digital design platform where AI agents, verification loops,
                  synthesis, and signoff all behave like managed tasks with clear ownership and status.
                </p>
              </div>
              <div className='flex flex-wrap items-center gap-2 xl:justify-end'>
                <Badge className='rounded-full bg-emerald-100 px-3 py-1 text-emerald-700 hover:bg-emerald-100'>
                  <MaterialIcon name='smart_toy' className='mr-1 text-[14px]' /> Agentic pipeline
                </Badge>
                <Badge className='rounded-full bg-indigo-100 px-3 py-1 text-indigo-700 hover:bg-indigo-100'>
                  <MaterialIcon name='view_in_ar' className='mr-1 text-[14px]' /> Browser-native
                </Badge>
                <Badge className='rounded-full bg-amber-100 px-3 py-1 text-amber-700 hover:bg-amber-100'>
                  <MaterialIcon name='deployed_code' className='mr-1 text-[14px]' /> Tapeout oriented
                </Badge>
              </div>
            </div>
          </section>

          <section className='rounded-3xl bg-white p-4 shadow-xl sm:p-5'>
            <Outlet />
          </section>
        </main>
      </div>
    </div>
  )
}
