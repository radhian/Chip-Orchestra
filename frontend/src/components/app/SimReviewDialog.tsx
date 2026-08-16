import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Image as ImageIcon, Terminal, Waves, XCircle } from 'lucide-react'

import { getSimReview, workspaceRawUrl } from '@/api/tasks'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import type { SimPreview, SimReview } from '@/types/orchestra'

/** One rendered SIM output. The desired/actual pair is the whole point of this
 *  gate, so they are shown at the same size and never cropped. */
function PreviewCard({ taskId, preview }: { taskId: string; preview: SimPreview }) {
  const accent =
    preview.role === 'chip'
      ? 'border-emerald-200'
      : preview.role === 'golden'
        ? 'border-amber-200'
        : 'border-slate-200'
  return (
    <figure className={`min-w-0 rounded-2xl border bg-white p-3 ${accent}`}>
      <figcaption className='mb-2 flex items-center gap-2 text-xs font-semibold text-slate-600'>
        {preview.role === 'waveform' ? (
          <Waves className='h-3.5 w-3.5 shrink-0' />
        ) : (
          <ImageIcon className='h-3.5 w-3.5 shrink-0' />
        )}
        <span className='truncate'>{preview.label}</span>
      </figcaption>
      <img
        src={workspaceRawUrl(taskId, preview.path)}
        alt={preview.label}
        className='max-h-72 w-full rounded-xl bg-slate-50 object-contain'
      />
      <p className='mt-2 truncate text-[11px] text-slate-400'>{preview.path}</p>
    </figure>
  )
}

/** The SIM human gate. Everything after this stage — synthesis, place & route,
 *  signoff — spends hours turning whatever the RTL already does into silicon,
 *  so the flow stops here and asks whether the CHIP's computed output matches
 *  the golden model's desired output. Rejecting sends the design back with the
 *  reviewer's note instead of hardening a design nobody confirmed. */
export function SimReviewDialog({
  taskId,
  open,
  onOpenChange,
  onApprove,
  onReject,
  refreshKey,
}: {
  taskId: string
  open: boolean
  onOpenChange: (next: boolean) => void
  onApprove: () => void
  onReject: (comment: string) => Promise<void> | void
  refreshKey: number
}) {
  const [review, setReview] = useState<SimReview | null>(null)
  const [loading, setLoading] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [comment, setComment] = useState('')

  useEffect(() => {
    if (!open || !taskId) return
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        const data = await getSimReview(taskId)
        if (!cancelled) setReview(data)
      } catch {
        if (!cancelled) setReview(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, taskId, refreshKey])

  const errors = review?.report?.errors ?? []
  const warnings = review?.report?.warnings ?? []
  const matched = Boolean(review?.hasGoldenMatch && review?.goldenMatch)
  const mismatched = Boolean(review?.hasGoldenMatch && !review?.goldenMatch)

  // Desired and actual side by side; the input and waveform below them.
  const [pair, rest] = useMemo(() => {
    const previews = review?.previews ?? []
    return [
      previews.filter((p) => p.role === 'golden' || p.role === 'chip'),
      previews.filter((p) => p.role !== 'golden' && p.role !== 'chip'),
    ]
  }, [review?.previews])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-h-[90vh] w-[min(56rem,95vw)] max-w-[95vw] overflow-y-auto overflow-x-hidden'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Terminal className='h-5 w-5 text-sky-500' />
            Simulation review
          </DialogTitle>
          <DialogDescription>
            The chip has been simulated against the approved golden model. Everything after this —
            synthesis, place &amp; route, signoff — spends hours hardening whatever the RTL already
            does, so confirm the result now: approve to start hardening, or reject to send the design
            back with your correction.
          </DialogDescription>
        </DialogHeader>

        {loading && !review ? (
          <p className='py-8 text-center text-sm text-slate-500'>Loading simulation results…</p>
        ) : !review?.available ? (
          <p className='py-8 text-center text-sm text-slate-500'>
            No simulation report on disk yet.
          </p>
        ) : (
          <div className='min-w-0 space-y-4'>
            {matched ? (
              <div className='flex items-start gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800'>
                <CheckCircle2 className='mt-0.5 h-4 w-4 shrink-0' />
                <span className='min-w-0 break-words'>
                  <strong>Chip output matches the golden model value-for-value.</strong>{' '}
                  {review.report?.summary}
                </span>
              </div>
            ) : mismatched ? (
              <div className='flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800'>
                <XCircle className='mt-0.5 h-4 w-4 shrink-0' />
                <span className='min-w-0 break-words'>
                  <strong>Chip output does NOT match the golden model.</strong> Hardening this would
                  commit the mismatch to silicon.
                </span>
              </div>
            ) : (
              <div className='flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800'>
                <AlertCircle className='mt-0.5 h-4 w-4 shrink-0' />
                <span className='min-w-0 break-words'>
                  No chip-vs-golden comparison was recorded — the testbench may not have dumped the
                  chip's output. {review.report?.summary}
                </span>
              </div>
            )}

            {errors.length > 0 && (
              <div className='min-w-0 rounded-2xl border border-rose-200 bg-rose-50 p-3'>
                <p className='mb-1 text-xs font-semibold text-rose-700'>Errors</p>
                <ul className='list-disc space-y-1 pl-5 text-xs break-words text-rose-700'>
                  {errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}
            {warnings.length > 0 && (
              <div className='min-w-0 rounded-2xl border border-amber-200 bg-amber-50 p-3'>
                <p className='mb-1 text-xs font-semibold text-amber-700'>Warnings</p>
                <ul className='list-disc space-y-1 pl-5 text-xs break-words text-amber-700'>
                  {warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {pair.length > 0 && (
              <div className='min-w-0'>
                <p className='mb-2 text-sm font-semibold text-slate-700'>Desired vs actual</p>
                <div className='grid min-w-0 gap-3 sm:grid-cols-2'>
                  {pair.map((p) => (
                    <PreviewCard key={p.path} taskId={taskId} preview={p} />
                  ))}
                </div>
              </div>
            )}
            {rest.length > 0 && (
              <div className='grid min-w-0 gap-3 sm:grid-cols-2'>
                {rest.map((p) => (
                  <PreviewCard key={p.path} taskId={taskId} preview={p} />
                ))}
              </div>
            )}

            {review.simLog && (
              <div className='min-w-0'>
                <p className='mb-2 text-sm font-semibold text-slate-700'>Testbench console</p>
                <pre className='max-h-64 w-full overflow-auto whitespace-pre-wrap break-all rounded-xl bg-slate-900 p-3 text-[11px] leading-5 text-slate-100'>
                  {review.simLog.slice(-6000)}
                </pre>
              </div>
            )}

            {rejecting && (
              <div>
                <p className='mb-2 text-sm font-semibold text-slate-700'>What is wrong?</p>
                <Textarea
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder='e.g. the output image is shifted by one row, or the UART never returns the last byte'
                  rows={3}
                />
              </div>
            )}
          </div>
        )}

        <DialogFooter className='gap-2 sm:justify-between'>
          <Badge variant='outline' className='self-center'>
            {review?.awaitingApproval ? 'Awaiting your approval' : review?.status || 'SIM'}
          </Badge>
          <div className='flex gap-2'>
            {rejecting ? (
              <>
                <Button variant='outline' onClick={() => setRejecting(false)}>
                  Cancel
                </Button>
                <Button
                  variant='destructive'
                  onClick={() => {
                    void onReject(comment)
                    setRejecting(false)
                    setComment('')
                  }}
                >
                  Send correction
                </Button>
              </>
            ) : (
              <>
                <Button variant='outline' onClick={() => setRejecting(true)}>
                  <XCircle className='mr-2 h-4 w-4' />
                  Result is wrong
                </Button>
                <Button onClick={onApprove}>
                  <CheckCircle2 className='mr-2 h-4 w-4' />
                  Result is correct — start hardening
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
