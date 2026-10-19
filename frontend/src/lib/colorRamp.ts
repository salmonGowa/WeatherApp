import type { HeatmapMetric } from '../types'
import { RISK_COLOR } from './risk'

export type RGBA = [number, number, number, number] // 0–255
export interface Stop {
  value: number
  color: RGBA
}

function hex(h: string, alpha: number): RGBA {
  const n = parseInt(h.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, Math.round(alpha * 255)]
}

/**
 * Ramp stops sit on the risk-table thresholds so the colour a viewer sees
 * in the wind/rain/snow views lines up with the risk classes.
 */
export const RAMPS: Record<HeatmapMetric, { stops: Stop[]; unit: string; ticks: number[] }> = {
  risk: {
    unit: '',
    ticks: [0, 1, 2, 3, 4],
    stops: [
      { value: 0, color: hex(RISK_COLOR.low, 0.18) },
      { value: 1, color: hex(RISK_COLOR.moderate, 0.5) },
      { value: 2, color: hex(RISK_COLOR.high, 0.62) },
      { value: 3, color: hex(RISK_COLOR.severe, 0.72) },
      { value: 4, color: hex(RISK_COLOR.no_travel, 0.8) },
    ],
  },
  wind: {
    unit: 'mph',
    ticks: [0, 25, 35, 45, 55],
    stops: [
      { value: 0, color: hex('#74c0fc', 0.08) },
      { value: 15, color: hex('#4dabf7', 0.35) },
      { value: 25, color: hex('#f2c200', 0.5) },
      { value: 35, color: hex('#f76707', 0.62) },
      { value: 45, color: hex('#e03131', 0.72) },
      { value: 55, color: hex('#862e9c', 0.8) },
    ],
  },
  rain: {
    unit: 'in/hr',
    ticks: [0, 0.1, 0.25, 0.5, 1],
    stops: [
      { value: 0, color: hex('#74c0fc', 0) },
      { value: 0.01, color: hex('#74c0fc', 0.3) },
      { value: 0.1, color: hex('#1c7ed6', 0.5) },
      { value: 0.25, color: hex('#f76707', 0.62) },
      { value: 0.5, color: hex('#e03131', 0.72) },
      { value: 1, color: hex('#862e9c', 0.8) },
    ],
  },
  snow: {
    unit: 'in/hr',
    ticks: [0, 0.5, 1, 2, 3],
    stops: [
      { value: 0, color: hex('#e7f5ff', 0) },
      { value: 0.05, color: hex('#a5d8ff', 0.35) },
      { value: 0.5, color: hex('#4dabf7', 0.55) },
      { value: 1, color: hex('#f76707', 0.62) },
      { value: 2, color: hex('#e03131', 0.72) },
      { value: 3, color: hex('#862e9c', 0.8) },
    ],
  },
}

/** Linear interpolation through the ramp; clamps at both ends. */
export function colorAt(stops: Stop[], value: number): RGBA {
  if (value <= stops[0].value) return stops[0].color
  for (let i = 1; i < stops.length; i++) {
    const b = stops[i]
    if (value <= b.value) {
      const a = stops[i - 1]
      const t = (value - a.value) / (b.value - a.value)
      return [0, 1, 2, 3].map((k) => Math.round(a.color[k] + t * (b.color[k] - a.color[k]))) as RGBA
    }
  }
  return stops[stops.length - 1].color
}

export function cssGradient(metric: HeatmapMetric): string {
  const { stops } = RAMPS[metric]
  const max = stops[stops.length - 1].value
  const parts = stops.map(({ value, color: [r, g, b, a] }) => {
    // legend shows colours a bit more opaque than on the map, for legibility
    const alpha = Math.min(1, a / 255 + 0.25).toFixed(2)
    return `rgba(${r},${g},${b},${alpha}) ${((value / max) * 100).toFixed(1)}%`
  })
  return `linear-gradient(to right, ${parts.join(', ')})`
}
