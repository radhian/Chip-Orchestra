import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createTask } from '@/api/tasks'
import { PlatformCreateSection, type LaunchForm } from '@/components/app/PlatformCreateSection'
import { PlatformLayout } from '@/components/app/PlatformLayout'
import type { CreateTaskInput, LaunchMode, ReviewGate } from '@/types/chiporchestra'

const initialForm: LaunchForm = {
  taskName: '',
  launchMode: 'FULL_FLOW_GATED',
  designBrief: '',
  pdk: 'sky130',
  reviewGate: 'BOTH',
  clockPeriodNs: '10',
  researchDepth: 'MEDIUM',
}

const stdcellFor: Record<string, string> = {
  sky130: 'sky130_fd_sc_hd',
  gf180: 'gf180mcu_fd_sc_mcu7t5v0',
}

function reviewGatesFor(value: string): ReviewGate[] {
  if (value === 'BEFORE_SYNTH') return ['BEFORE_SYNTH']
  if (value === 'BEFORE_SIGNOFF') return ['BEFORE_SIGNOFF']
  return ['BEFORE_SYNTH', 'BEFORE_SIGNOFF']
}

export function PlatformCreateTaskPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<LaunchForm>(initialForm)
  const [creating, setCreating] = useState(false)

  function onChange(patch: Partial<LaunchForm>) {
    setForm((prev) => ({ ...prev, ...patch }))
  }

  async function handleCreateTask() {
    const clockPeriod = Number.parseFloat(form.clockPeriodNs)
    const payload: CreateTaskInput = {
      task: {
        name: form.taskName.trim(),
        launch_mode: form.launchMode as LaunchMode,
        design_brief: form.designBrief.trim(),
        repo_mode: 'TEMPLATE',
        template_id: 'digital-block-starter',
        pdk_id: form.pdk,
        stdcell_lib_id: stdcellFor[form.pdk] ?? 'sky130_fd_sc_hd',
        review_gates: reviewGatesFor(form.reviewGate),
        agent_policy: {
          autonomy_level: 'BALANCED',
          retry_budget: 3,
          auto_apply_patches: true,
        },
        clock_period_ns: Number.isFinite(clockPeriod) ? clockPeriod : 10,
        research_depth: form.researchDepth,
      },
    }

    setCreating(true)
    try {
      const task = await createTask(payload)
      navigate(`/tasks/${task.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <PlatformLayout activeSection='create' detailHref='/tasks/new'>
      <PlatformCreateSection
        form={form}
        creating={creating}
        onChange={onChange}
        onSubmit={() => void handleCreateTask()}
      />
    </PlatformLayout>
  )
}
