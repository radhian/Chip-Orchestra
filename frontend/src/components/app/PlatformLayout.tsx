import type { ReactNode } from 'react'

import { PlatformSidebar } from '@/components/app/PlatformSidebar'

type HeroBadge = {
  icon: string
  label: string
  className: string
}

const heroBadges: HeroBadge[] = [
  { icon: 'smart_toy', label: 'Agentic pipeline', className: 'bg-[#e7fbf4] text-[#139d82]' },
  { icon: 'view_in_ar', label: 'Browser-native', className: 'bg-[#eef2ff] text-[#5b5bd6]' },
  { icon: 'deployed_code', label: 'Tapeout oriented', className: 'bg-[#fff3df] text-[#c77a00]' },
]

export function PlatformLayout({
  activeSection,
  detailHref,
  children,
}: {
  activeSection: 'overview' | 'create' | 'detail'
  detailHref?: string
  children: ReactNode
}) {
  return (
    <div className='min-h-screen bg-[#f3f6fb] px-3 py-4 text-slate-800 sm:px-4 lg:px-5'>
      <div className='mx-auto flex max-w-[1760px] flex-col gap-4 xl:flex-row xl:items-start'>
        <PlatformSidebar activeSection={activeSection} detailHref={detailHref} />

        <main className='min-w-0 flex-1 space-y-4'>
          <section className='rounded-[30px] bg-white px-5 py-6 shadow-[0_24px_80px_rgba(148,163,184,0.18)] sm:px-6'>
            <div className='flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between'>
              <div className='max-w-4xl'>
                <p className='text-sm font-medium text-slate-400'>AI-native digital chip design</p>
                <h2 className='mt-2 text-[2.35rem] font-semibold tracking-tight text-slate-900'>Chip Orchestra digital IC platform</h2>
                <p className='mt-3 max-w-4xl text-sm leading-7 text-slate-500 sm:text-base'>
                  A browser-native platform where AI agents generate, verify, and harden RTL from a natural-language
                  brief — every run tracked as a managed task with live logs, artifacts, and signoff.
                </p>
              </div>

              <div className='flex flex-wrap items-center gap-2 xl:justify-end'>
                {heroBadges.map((badge) => (
                  <span
                    key={badge.label}
                    className={`inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold ${badge.className}`}
                  >
                    <span className='material-symbols-outlined mr-1 text-[16px]' aria-hidden='true'>
                      {badge.icon}
                    </span>
                    {badge.label}
                  </span>
                ))}
              </div>
            </div>
          </section>

          <section className='rounded-[30px] bg-white p-5 shadow-[0_24px_80px_rgba(148,163,184,0.18)] sm:p-6'>{children}</section>
        </main>
      </div>
    </div>
  )
}
