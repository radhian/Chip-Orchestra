import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createTask } from '@/api/tasks'
import { PlatformCreateSection } from '@/components/app/PlatformCreateSection'
import { PlatformLayout } from '@/components/app/PlatformLayout'
import type { CreateTaskInput } from '@/types/chiporchestra'

const launchForm = {
  taskName: 'fft_accelerator_1024p digital flow',
  launchMode: 'Full flow with gated approvals',
  designBrief: 'Streaming FFT accelerator, AXI-lite config, throughput > 500 MHz target, moderate area sensitivity.',
  repositorySource:
    'Link `git@repo/chiporchestra/fft-accelerator.git` or create a new repo from the `digital-block-starter` template.',
  bootstrapOption: 'Use template: digital-block-starter',
  pdkLibrary: 'Sky130 HD + SRAM macro pack',
  reviewGate: 'Require engineer approval before synthesis and before signoff packaging',
}

export function PlatformCreateTaskPage() {
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)

  async function handleCreateTask() {
    const payload: CreateTaskInput = {
      task: {
        name: launchForm.taskName,
        launch_mode: 'FULL_FLOW_GATED',
        design_brief: launchForm.designBrief,
        repo_id: 'git@repo/chiporchestra/fft-accelerator.git',
        repo_branch: 'main',
        repo_mode: 'EXISTING',
        template_id: 'digital-block-starter',
        pdk_id: 'sky130',
        stdcell_lib_id: 'gf180-mixed-eval',
        review_gates: ['BEFORE_SYNTH', 'BEFORE_SIGNOFF'],
        agent_policy: {
          autonomy_level: 'BALANCED',
          retry_budget: 2,
          auto_apply_patches: true,
        },
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
    <PlatformLayout activeSection='create' detailHref='/tasks/fft-1024p'>
      <PlatformCreateSection form={launchForm} creating={creating} onSubmit={() => void handleCreateTask()} />
    </PlatformLayout>
  )
}
