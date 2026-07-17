import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Loader2 } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <Card className='rounded-3xl border-dashed border-slate-300 shadow-none'>
      <CardContent className='p-8 text-center'>
        <h3 className='text-lg font-semibold text-slate-900'>{title}</h3>
        <p className='mt-2 text-sm leading-6 text-slate-500'>{detail}</p>
      </CardContent>
    </Card>
  )
}

export function LoadingState({ label = 'Loading Chip Orchestra data…' }: { label?: string }) {
  return (
    <Card className='rounded-3xl border-slate-200 shadow-none'>
      <CardContent className='flex items-center gap-3 p-8 text-sm text-slate-500'>
        <Loader2 className='h-4 w-4 animate-spin text-blue-600' />
        <span>{label}</span>
      </CardContent>
    </Card>
  )
}

export function ErrorState({
  title,
  detail,
  onRetry,
}: {
  title: string
  detail: string
  onRetry?: () => void
}) {
  return (
    <Card className='rounded-3xl border-rose-200 bg-rose-50 shadow-none'>
      <CardContent className='space-y-4 p-6'>
        <div>
          <h3 className='text-lg font-semibold text-rose-700'>{title}</h3>
          <p className='mt-2 text-sm leading-6 text-rose-700/80'>{detail}</p>
        </div>
        {onRetry ? (
          <button
            onClick={onRetry}
            className='rounded-2xl bg-rose-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-rose-700'
          >
            Retry
          </button>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function SummaryRow({
  icon: Icon,
  title,
  value,
}: {
  icon: LucideIcon
  title: string
  value: string
}) {
  return (
    <div className='flex items-start gap-3'>
      <div className='flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-600'>
        <Icon className='h-4 w-4' />
      </div>
      <div>
        <p className='text-sm font-medium text-slate-500'>{title}</p>
        <p className='mt-1 text-sm font-semibold leading-6 text-slate-900'>{value}</p>
      </div>
    </div>
  )
}

export function MetricCard({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string
  icon: LucideIcon
}) {
  return (
    <Card className='rounded-2xl border-slate-200 bg-slate-50 shadow-none'>
      <CardContent className='flex items-start justify-between gap-2 p-4'>
        <div className='min-w-0'>
          <p className='text-xs uppercase tracking-widest text-slate-400'>{label}</p>
          <p className='mt-3 break-words text-lg font-semibold leading-snug text-slate-900'>{value}</p>
        </div>
        <div className='flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-slate-600 shadow-sm'>
          <Icon className='h-4 w-4' />
        </div>
      </CardContent>
    </Card>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint: string
  children: ReactNode
}) {
  return (
    <div className='space-y-2'>
      <div>
        <p className='text-sm font-semibold text-slate-900'>{label}</p>
        <p className='mt-1 text-sm text-slate-500'>{hint}</p>
      </div>
      {children}
    </div>
  )
}
