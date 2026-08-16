import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  FileCode2,
  Image as ImageIcon,
  Upload,
  Waves,
  XCircle,
} from 'lucide-react'

import { getHwSwReview, uploadHwSwInput, workspaceRawUrl } from '@/api/tasks'
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
import type { HwSwReview, SimPreview } from '@/types/orchestra'

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

/** The HW/SW verification gate.
 *
 *  SIM asks "does the RTL match the golden model on the input we baked in?".
 *  This asks the question the user actually has: "if I hand this chip MY file
 *  over its real interface, do I get the right thing back?" — so the dialog
 *  leads with an upload button. Choosing a file re-runs the whole bridge
 *  (encode → drive the DUT → decode) against it, and the decoded result comes
 *  back here to be judged. */
export function HwSwReviewDialog({
  taskId,
  open,
  onOpenChange,
  onApprove,
  onReject,
  onRerun,
  refreshKey,
}: {
  taskId: string
  open: boolean
  onOpenChange: (next: boolean) => void
  onApprove: () => void
  onReject: (comment: string) => Promise<void> | void
  onRerun?: () => void
  refreshKey: number
}) {
  const [review, setReview] = useState<HwSwReview | null>(null)
  const [loading, setLoading] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [comment, setComment] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadNotice, setUploadNotice] = useState('')
  const [openSource, setOpenSource] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open || !taskId) return
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        const data = await getHwSwReview(taskId)
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

  const report = review?.report
  const metrics = (report?.metrics ?? {}) as Record<string, unknown>
  const errors = report?.errors ?? []
  const matched = Boolean(review?.hasMatch && review?.match)
  const mismatched = Boolean(review?.hasMatch && !review?.match)
  const iface = report?.interface

  const [pair, rest] = useMemo(() => {
    const previews = review?.previews ?? []
    return [
      previews.filter((p) => p.role === 'golden' || p.role === 'chip'),
      previews.filter((p) => p.role !== 'golden' && p.role !== 'chip'),
    ]
  }, [review?.previews])

  async function handleUpload(file: File) {
    setUploadError(null)
    setUploadNotice('')
    setUploading(true)
    try {
      await uploadHwSwInput(taskId, file)
      setUploadNotice(
        `“${file.name}” is being sent through the chip — the host driver encodes it, the ` +
          'interface bench drives the RTL with it, and the decoded result appears here when the ' +
          'stage finishes.',
      )
      onRerun?.()
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-h-[90vh] w-[min(60rem,95vw)] max-w-[95vw] overflow-y-auto overflow-x-hidden'>
        <DialogHeader>
          <DialogTitle className='flex items-center gap-2'>
            <Cpu className='h-5 w-5 text-violet-500' />
            Hardware / software verification
          </DialogTitle>
          <DialogDescription>
            The chip was driven the way real software will drive it: a generated Python host driver
            encoded the input into the frames the top-level RTL speaks, a generated Verilog interface
            bench replayed them against the unmodified design, and the driver decoded what came back.
            Upload your own input to verify it again, then approve the result or reject it with a
            correction.
          </DialogDescription>
        </DialogHeader>

        <div className='min-w-0 space-y-4'>
          {/* Upload first: this gate is about YOUR input, so the action that
              changes the answer leads rather than hides under the results. */}
          <div className='rounded-2xl border border-violet-200 bg-violet-50 p-4'>
            <p className='text-sm font-semibold text-violet-900'>Send an input through the chip</p>
            <p className='mt-1 text-xs leading-5 text-violet-800'>
              Any image, <code>.mem</code> hex dump or raw byte file. Images are converted to the
              chip's sample format and geometry automatically
              {iface?.constants?.IMG_W ? ` (${iface.constants.IMG_W}×${iface.constants.IMG_H ?? iface.constants.IMG_W} samples)` : ''}
              . Uploading re-runs the verification immediately.
            </p>
            <div className='mt-3 flex flex-wrap items-center gap-3'>
              <input
                ref={fileInput}
                type='file'
                className='hidden'
                onChange={(event) => {
                  const file = event.target.files?.[0]
                  event.target.value = ''
                  if (file) void handleUpload(file)
                }}
              />
              <Button
                onClick={() => fileInput.current?.click()}
                disabled={uploading}
                className='rounded-2xl bg-violet-600 hover:bg-violet-700'
              >
                <Upload className='mr-2 h-4 w-4' />
                {uploading ? 'Uploading…' : 'Upload input & verify'}
              </Button>
              {review?.inputName ? (
                <span className='text-xs text-violet-800'>
                  Current input: <span className='font-semibold'>{review.inputName}</span>
                </span>
              ) : null}
            </div>
            {uploadNotice ? <p className='mt-3 text-xs leading-5 text-violet-900'>{uploadNotice}</p> : null}
            {uploadError ? <p className='mt-3 text-xs text-rose-700'>{uploadError}</p> : null}
          </div>

          {loading && !review ? (
            <p className='py-8 text-center text-sm text-slate-500'>Loading verification results…</p>
          ) : !review?.available ? (
            <p className='py-8 text-center text-sm text-slate-500'>
              No verification report on disk yet — upload an input above to run the first one.
            </p>
          ) : (
            <>
              {matched ? (
                <div className='flex items-start gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800'>
                  <CheckCircle2 className='mt-0.5 h-4 w-4 shrink-0' />
                  <span className='min-w-0 break-words'>
                    <strong>The chip returned exactly what the golden model computes for this input.</strong>{' '}
                    {report?.summary}
                  </span>
                </div>
              ) : mismatched ? (
                <div className='flex items-start gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800'>
                  <XCircle className='mt-0.5 h-4 w-4 shrink-0' />
                  <span className='min-w-0 break-words'>
                    <strong>The chip's response does NOT match the golden model.</strong> {report?.summary}
                  </span>
                </div>
              ) : (
                <div className='flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800'>
                  <AlertCircle className='mt-0.5 h-4 w-4 shrink-0' />
                  <span className='min-w-0 break-words'>{report?.summary}</span>
                </div>
              )}

              {errors.length > 0 && (
                <div className='min-w-0 rounded-2xl border border-rose-200 bg-rose-50 p-3'>
                  <p className='mb-1 text-xs font-semibold text-rose-700'>Errors</p>
                  <ul className='list-disc space-y-1 break-words pl-5 text-xs text-rose-700'>
                    {errors.map((message, index) => (
                      <li key={index}>{message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {iface?.description ? (
                <div className='min-w-0 rounded-2xl border border-slate-200 bg-slate-50 p-3'>
                  <p className='mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500'>
                    Detected chip interface
                  </p>
                  <p className='text-xs leading-5 text-slate-700'>{iface.description}</p>
                  <p className='mt-2 text-[11px] text-slate-500'>
                    Software: <code>{iface.driver}</code> ({iface.driver_origin}) · Hardware:{' '}
                    <code>{iface.testbench}</code> ({iface.testbench_origin})
                  </p>
                </div>
              ) : null}

              {pair.length > 0 && (
                <div className='min-w-0'>
                  <p className='mb-2 text-sm font-semibold text-slate-700'>Expected vs what the chip returned</p>
                  <div className='grid min-w-0 gap-3 sm:grid-cols-2'>
                    {pair.map((preview) => (
                      <PreviewCard key={preview.path} taskId={taskId} preview={preview} />
                    ))}
                  </div>
                </div>
              )}
              {rest.length > 0 && (
                <div className='grid min-w-0 gap-3 sm:grid-cols-2'>
                  {rest.map((preview) => (
                    <PreviewCard key={preview.path} taskId={taskId} preview={preview} />
                  ))}
                </div>
              )}

              {Object.keys(metrics).length > 0 && (
                <div className='min-w-0 overflow-x-auto rounded-2xl border border-slate-200'>
                  <table className='w-full text-left text-xs'>
                    <tbody>
                      {Object.entries(metrics).map(([key, value]) => (
                        <tr key={key} className='border-b border-slate-100 last:border-0'>
                          <td className='px-3 py-2 font-medium text-slate-700'>{key}</td>
                          <td className='px-3 py-2 text-slate-600'>{value === null ? '—' : String(value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {review.sources.length > 0 && (
                <div className='min-w-0 space-y-2'>
                  <p className='text-sm font-semibold text-slate-700'>The generated interface</p>
                  {review.sources.map((source) => (
                    <div key={source.path} className='overflow-hidden rounded-2xl border border-slate-200'>
                      <button
                        type='button'
                        onClick={() => setOpenSource((current) => (current === source.path ? '' : source.path))}
                        className='flex w-full items-center gap-2 bg-slate-50 px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-100'
                      >
                        <FileCode2 className='h-3.5 w-3.5 shrink-0' />
                        <span className='truncate'>{source.label}</span>
                        <code className='ml-auto shrink-0 text-[11px] text-slate-400'>{source.path}</code>
                      </button>
                      {openSource === source.path ? (
                        <pre className='max-h-72 overflow-auto whitespace-pre bg-slate-900 p-3 text-[11px] leading-5 text-slate-100'>
                          {source.content}
                        </pre>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}

              {review.consoleLog && (
                <div className='min-w-0'>
                  <p className='mb-2 text-sm font-semibold text-slate-700'>Co-simulation console</p>
                  <pre className='max-h-64 w-full overflow-auto whitespace-pre-wrap break-all rounded-xl bg-slate-900 p-3 text-[11px] leading-5 text-slate-100'>
                    {review.consoleLog.slice(-6000)}
                  </pre>
                </div>
              )}
            </>
          )}

          {rejecting && (
            <div>
              <p className='mb-2 text-sm font-semibold text-slate-700'>What is wrong?</p>
              <Textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder='e.g. the returned image is shifted one row down, or the last row of the picture never comes back over the UART'
                rows={3}
              />
            </div>
          )}
        </div>

        <DialogFooter className='gap-2 sm:justify-between'>
          <Badge variant='outline' className='self-center'>
            {review?.awaitingApproval ? 'Awaiting your approval' : review?.status || 'HW_SW_VERIFY'}
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
                  Result is correct — continue
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
