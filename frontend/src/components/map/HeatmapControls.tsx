import { Pause, Play, Truck } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { cssGradient, RAMPS } from '../../lib/colorRamp'
import { formatTime, timeZoneLabel } from '../../lib/format'
import { RISK_LABEL, RISK_LEVELS } from '../../lib/risk'
import { checkbox, hiddenRadio, segment, spinner, toggle } from '../../lib/ui'
import type { HeatmapMetric, HeatmapResponse } from '../../types'

const METRICS: { id: HeatmapMetric; label: string }[] = [
  { id: 'risk', label: 'Risk' },
  { id: 'wind', label: 'Wind' },
  { id: 'rain', label: 'Rain' },
  { id: 'snow', label: 'Snow' },
]
const PLAY_HOURS_PER_SECOND = 4

interface Props {
  heatmap: HeatmapResponse | null
  loading: boolean
  error: string | null
  visible: boolean
  onVisibleChange: (v: boolean) => void
  metric: HeatmapMetric
  onMetricChange: (m: HeatmapMetric) => void
  hour: number
  onHourChange: (h: number) => void
  arrivalHour: number | null
}

export default function HeatmapControls({
  heatmap,
  loading,
  error,
  visible,
  onVisibleChange,
  metric,
  onMetricChange,
  hour,
  onHourChange,
  arrivalHour,
}: Props) {
  const [playing, setPlaying] = useState(false)
  const hourRef = useRef(hour)
  const max = heatmap?.hours ?? 48

  useEffect(() => {
    hourRef.current = hour
  }, [hour])

  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    let next = hourRef.current
    const tick = (now: number) => {
      next += ((now - last) / 1000) * PLAY_HOURS_PER_SECOND
      last = now
      if (next >= max) {
        onHourChange(max)
        setPlaying(false)
        return
      }
      onHourChange(next)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, max, onHourChange])

  const ramp = RAMPS[metric]
  const time = heatmap ? Date.parse(heatmap.start) + hour * 3_600_000 : null

  return (
    <div
      className="absolute bottom-6 left-4 z-1000 flex w-[min(460px,calc(100%-32px))] flex-col gap-2 rounded-[10px] bg-panel px-3.5 pt-2.5 pb-3 shadow-float"
      aria-label="Weather heatmap controls"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className={toggle}>
          <input type="checkbox" className={checkbox} checked={visible} onChange={(e) => onVisibleChange(e.target.checked)} />
          Weather heatmap
        </label>
        <div className="inline-flex" role="radiogroup" aria-label="Heatmap layer">
          {METRICS.map((m) => (
            <label key={m.id} className={segment(true)}>
              <input
                type="radio"
                name="metric"
                className={hiddenRadio}
                checked={metric === m.id}
                onChange={() => onMetricChange(m.id)}
              />
              {m.label}
            </label>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-[12.5px] text-muted">
          <span className={spinner} aria-hidden /> Loading corridor forecast…
        </div>
      )}
      {error && <div className="text-[12.5px] text-danger">{error}</div>}

      {heatmap && (
        <>
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              className="grid size-8 flex-none cursor-pointer place-items-center rounded-full bg-accent text-accent-ink"
              aria-label={playing ? 'Pause' : 'Play forecast'}
              onClick={() => {
                if (!playing && hour >= max) onHourChange(0)
                setPlaying(!playing)
              }}
            >
              {playing ? (
                <Pause className="size-3.5 fill-current" aria-hidden />
              ) : (
                <Play className="ml-0.5 size-3.5 fill-current" aria-hidden />
              )}
            </button>
            <div className="relative flex flex-1 items-center">
              <input
                type="range"
                className="m-0 w-full accent-accent"
                min={0}
                max={max}
                step={0.25}
                value={hour}
                onChange={(e) => {
                  setPlaying(false)
                  onHourChange(Number(e.target.value))
                }}
                aria-label="Forecast hour"
                aria-valuetext={`plus ${Math.floor(hour)} hours`}
              />
              {arrivalHour !== null && arrivalHour <= max && (
                <span
                  className="pointer-events-none absolute -top-1.5 h-2 w-0.5 -translate-x-px bg-ink"
                  style={{ left: `${(arrivalHour / max) * 100}%` }}
                  title="Selected route arrival"
                />
              )}
            </div>
            <div className="flex min-w-24.5 flex-col items-end text-xs/tight tabular-nums">
              <b className="text-sm">+{Math.floor(hour)}h</b>
              <span>
                {time && formatTime(time)} {timeZoneLabel}
              </span>
            </div>
          </div>

          <div>
            <div className="h-2.5 rounded-[5px] border border-line" style={{ background: cssGradient(metric) }} />
            <div className="relative h-4 text-[10.5px] text-muted">
              {ramp.ticks.map((t, i) => (
                <span
                  key={t}
                  className="absolute -translate-x-1/2 whitespace-nowrap first:translate-x-0 last:-translate-x-full"
                  style={{ left: `${(t / ramp.ticks[ramp.ticks.length - 1]) * 100}%` }}
                >
                  {metric === 'risk' ? RISK_LABEL[RISK_LEVELS[i]] : t}
                </span>
              ))}
            </div>
            <div className="text-[11px] text-muted">
              {metric === 'risk' ? (
                `Risk for this load · ${heatmap.corridor_miles} mi corridor · ~${Math.round(heatmap.grid.cell_km)} km cells`
              ) : (
                <>
                  {ramp.unit} · hour 0 = departure ·{' '}
                  <Truck className="inline size-3.5 align-[-3px]" aria-label="Truck icon" /> = selected route position
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
