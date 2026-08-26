import { useCallback, useEffect, useRef, useState } from 'react'

// Poll a background-job status endpoint. The heavy runs (calibrate, prospects,
// retrospective calibration) run in a worker thread on the API; this hook starts
// one and follows its progress, so the UI shows "in corso da X min (strumento
// k/13)" with a disabled button — never a red "già in corso" error.
//
//   fetchStatus() -> { data: {state, elapsed_sec, progress, total, step,
//                             result, error, duration_sec, stale}, error }
//   trigger()     -> POST helper that starts the job -> { data, error }
//   onDone(data)  -> called once on the running->done transition (reload data)
export function useJobStatus(fetchStatus, trigger, onDone) {
  const [status, setStatus] = useState(null)
  const [err, setErr] = useState(null)
  const timer = useRef(null)
  const prevState = useRef(null)
  const doneRef = useRef(onDone)
  doneRef.current = onDone

  const poll = useCallback(async () => {
    const { data, error } = await fetchStatus()
    if (error) { setErr(error.message); return null }
    setStatus(data)
    if (data?.state === 'done' && prevState.current === 'running') doneRef.current?.(data)
    prevState.current = data?.state
    return data
  }, [fetchStatus])

  const schedule = useCallback((data) => {
    clearTimeout(timer.current)
    if (data?.state === 'running') {
      timer.current = setTimeout(async () => { schedule(await poll()) }, 2000)
    }
  }, [poll])

  // On mount (and after navigation) pick up a job that may already be running.
  useEffect(() => {
    let alive = true
    poll().then((d) => { if (alive) schedule(d) })
    return () => { alive = false; clearTimeout(timer.current) }
  }, [poll, schedule])

  const start = useCallback(async () => {
    setErr(null)
    const { error } = await trigger()
    // A 409 "già in corso" is not an error for the user — just latch onto the
    // running job and start polling it.
    const d = await poll()
    if (!d && error) { setErr(error.message); return }
    schedule(d)
  }, [trigger, poll, schedule])

  return { status, err, start, running: status?.state === 'running' }
}

// Human summary of a running job: "in corso da 3 min · strumento 4/13 (NVDA)".
export function runningLabel(status) {
  if (!status || status.state !== 'running') return ''
  const mins = Math.max(0, Math.floor((status.elapsed_sec || 0) / 60))
  const parts = [`in corso da ${mins} min`]
  if (status.total) parts.push(`strumento ${(status.progress ?? 0) + 1}/${status.total}${status.step ? ` (${status.step})` : ''}`)
  if (status.stale) parts.push('⚠ sembra bloccato')
  return parts.join(' · ')
}

// Human summary of a finished job: outcome + timestamp + duration.
export function doneLabel(status, describe) {
  if (!status || status.state !== 'done') return ''
  const dur = status.duration_sec != null ? ` in ${Math.round(status.duration_sec)}s` : ''
  const when = status.finished_at ? ` · ${new Date(status.finished_at).toLocaleTimeString()}` : ''
  return `${describe ? describe(status.result) : 'Completato'}${dur}${when}`
}
