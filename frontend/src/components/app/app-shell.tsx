import type { ReactNode } from 'react'

export function AppShell({ sidebarSlot, children }: { sidebarSlot: ReactNode; children: ReactNode }) {
  return (
    <div className='min-h-screen bg-slate-100 text-slate-800'>
      <div className='flex min-h-screen w-full gap-3 p-2 sm:gap-4 sm:p-3 lg:p-4'>
        <aside className='hidden w-72 shrink-0 rounded-3xl bg-white p-4 shadow-xl lg:block'>{sidebarSlot}</aside>
        <main className='flex-1 rounded-3xl bg-white p-4 shadow-xl sm:p-5'>{children}</main>
      </div>
    </div>
  )
}
