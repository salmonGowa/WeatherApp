import { describe, expect, it } from 'vitest'
import type { Checkpoint, Stop } from '../types'
import { colorAt, RAMPS } from './colorRamp'
import { formatDuration } from './format'
import { buildTimeline, downsample, positionAt } from './timeline'

const cp = (lat: number, lon: number, eta: string) => ({ lat, lon, eta }) as Checkpoint

describe('timeline', () => {
  const checkpoints = [cp(40, -100, '2026-01-01T00:00:00Z'), cp(40, -98, '2026-01-01T02:00:00Z')]

  it('interpolates between checkpoint ETAs', () => {
    const tl = buildTimeline(checkpoints)
    expect(positionAt(tl, Date.parse('2026-01-01T01:00:00Z'))).toEqual([40, -99])
    expect(positionAt(tl, Date.parse('2025-12-31T23:00:00Z'))).toBeNull()
    expect(positionAt(tl, Date.parse('2026-01-01T03:00:00Z'))).toBeNull()
  })

  it('keeps the truck parked during a stop', () => {
    const stop = { lat: 40, lon: -99, start: '2026-01-01T01:00:00Z', end: '2026-01-01T01:30:00Z' } as Stop
    const tl = buildTimeline(
      [cp(40, -100, '2026-01-01T00:00:00Z'), cp(40, -98, '2026-01-01T02:30:00Z')],
      [stop],
    )
    expect(positionAt(tl, Date.parse('2026-01-01T01:15:00Z'))).toEqual([40, -99])
    expect(positionAt(tl, Date.parse('2026-01-01T02:00:00Z'))).toEqual([40, -98.5])
  })

  it('downsamples keeping both ends', () => {
    const pts = Array.from({ length: 101 }, (_, i) => i)
    const out = downsample(pts, 11)
    expect(out).toHaveLength(11)
    expect(out[0]).toBe(0)
    expect(out[10]).toBe(100)
  })
})

describe('colorAt', () => {
  const { stops } = RAMPS.wind
  it('clamps and hits stops exactly', () => {
    expect(colorAt(stops, -5)).toEqual(stops[0].color)
    expect(colorAt(stops, 25)).toEqual(stops[2].color)
    expect(colorAt(stops, 999)).toEqual(stops[stops.length - 1].color)
  })
  it('interpolates between stops', () => {
    const mid = colorAt(stops, 30)
    for (let k = 0; k < 4; k++) {
      const [lo, hi] = [stops[2].color[k], stops[3].color[k]].sort((a, b) => a - b)
      expect(mid[k]).toBeGreaterThanOrEqual(lo)
      expect(mid[k]).toBeLessThanOrEqual(hi)
    }
  })
})

describe('formatDuration', () => {
  it('formats hours and minutes', () => {
    expect(formatDuration(0.5)).toBe('30 min')
    expect(formatDuration(2)).toBe('2 h')
    expect(formatDuration(28.28)).toBe('28 h 17 min')
  })
})
