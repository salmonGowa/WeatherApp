import { formatTime } from '../../lib/format'
import { RISK_COLOR, RISK_LABEL } from '../../lib/risk'
import { riskBadge } from '../../lib/ui'
import type { Checkpoint, PlannedRoute, Stop } from '../../types'

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)


const MUTED = 'text-slate-500'
const CELL = 'border-t border-slate-200 px-1 py-0.75 text-left'

const badge = (level: Checkpoint['risk']['level']) =>
  `<span class="${riskBadge}" style="--risk:${RISK_COLOR[level]}">${RISK_LABEL[level]}</span>`

export function checkpointTooltip(route: PlannedRoute, cp: Checkpoint): string {
  const drivers = cp.risk.drivers.length ? ` · ${cp.risk.drivers.join(', ')}` : ''
  return `<strong>${esc(route.name)} · mile ${cp.mile}</strong><br/>${formatTime(cp.eta)} · ${
    RISK_LABEL[cp.risk.level]
  }${drivers}`
}

export function checkpointPopup(route: PlannedRoute, cp: Checkpoint): string {
  const w = cp.weather
  const rows = cp.risk.factors
    .map((f) => {
      const note = f.load_adjusted ? ` <span class="${MUTED}">(load rule)</span>` : ''
      return `<tr><td class="${CELL} capitalize">${f.condition}</td><td class="${CELL}">${f.value} ${f.unit}</td><td class="${CELL}">${badge(f.level)}${note}</td></tr>`
    })
    .join('')
  const position =
    cp.index === 0 ? 'Origin' : cp.index === route.checkpoints.length - 1 ? 'Destination' : `Checkpoint ${cp.index}`
  return `
    <div class="min-w-57.5 text-[12.5px]">
      <div class="mb-1.5 flex items-center gap-2 font-semibold">${badge(cp.risk.level)} <span>${esc(route.name)} · ${position}</span></div>
      <dl class="m-0 mb-2 grid grid-cols-[auto_1fr] gap-x-2.5 gap-y-0.5 [&_dd]:m-0 [&_dt]:text-slate-500">
        <dt>Mile</dt><dd>${cp.mile} <span class="${MUTED}">(covers ${cp.covers[0].toFixed(1)}–${cp.covers[1].toFixed(1)})</span></dd>
        <dt>ETA</dt><dd>${formatTime(cp.eta)}</dd>
        <dt>Gusts</dt><dd>${w.gust_mph} mph <span class="${MUTED}">(info only)</span></dd>
      </dl>
      <table class="w-full border-collapse">
        <thead><tr><th class="${CELL} font-semibold ${MUTED}">Condition</th><th class="${CELL} font-semibold ${MUTED}">Forecast</th><th class="${CELL} font-semibold ${MUTED}">Risk</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`
}

export function stopTooltip(stop: Stop): string {
  const label = stop.kind === 'rest' ? '10-hour rest (HOS)' : '30-minute break (HOS)'
  return `<strong>${label}</strong><br/>Mile ${stop.mile} · ${formatTime(stop.start)} – ${formatTime(stop.end)}`
}
