import type { ReactNode } from 'react'

import { Card, CardContent } from '@/components/ui/card'

export function MaterialIcon({ name, className = '' }: { name: string; className?: string }) {
  return <span className={`material-symbols-outlined ${className}`.trim()} aria-hidden='true'>{name}</span>
}

export function AnchorPill({
  label,
  icon,
  target,
  active = false,
}: {
  label: string
  icon: string
  target: string
  active?: boolean
}) {
  return (
    <a
      href={`#${target}`}
      className={`flex items-center justify-center gap-2 rounded-[18px] px-4 py-3 text-sm font-semibold transition ${
        active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      <MaterialIcon name={icon} className='text-[18px]' />
      {label}
    </a>
  )
}

export function MiniPanel({
  title,
  subtitle,
  badge,
  children,
}: {
  title: string
  subtitle: string
  badge: string
  children: ReactNode
}) {
  return (
    <Card className='rounded-[28px] border border-slate-200 shadow-none'>
      <CardContent className='space-y-4 p-5'>
        <div className='flex items-start justify-between gap-3'>
          <div>
            <p className='text-lg font-semibold text-slate-900'>{title}</p>
            <p className='mt-1 text-sm leading-6 text-slate-500'>{subtitle}</p>
          </div>
          <StagePill label={badge} tone='neutral' />
        </div>
        {children}
      </CardContent>
    </Card>
  )
}

export function ChecklistCard({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <div className='rounded-[24px] border border-slate-200 p-5'>
      <div className='flex items-start gap-3'>
        <div className='mt-0.5'>{icon}</div>
        <div>
          <p className='font-semibold text-slate-900'>{title}</p>
          <p className='mt-2 text-sm leading-6 text-slate-500'>{detail}</p>
        </div>
      </div>
    </div>
  )
}

export function StagePill({ label, tone }: { label: string; tone: 'running' | 'done' | 'review' | 'neutral' }) {
  const className =
    tone === 'running'
      ? 'bg-[#ecebff] text-[#5b5bd6]'
      : tone === 'done'
        ? 'bg-[#e7fbf4] text-[#129b80]'
        : tone === 'review'
          ? 'bg-[#fff3df] text-[#c77a00]'
          : 'bg-[#f1f5f9] text-slate-500'

  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${className}`}>{label}</span>
}
