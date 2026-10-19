import type { Checkpoint, LatLng, Stop } from '../types'

interface Keyframe {
  t: number
  pos: LatLng
}

export function buildTimeline(checkpoints: Checkpoint[], stops: Stop[] = []): Keyframe[] {
  const frames: Keyframe[] = checkpoints.map((c) => ({ t: Date.parse(c.eta), pos: [c.lat, c.lon] }))
  for (const s of stops) {
    frames.push({ t: Date.parse(s.start), pos: [s.lat, s.lon] })
    frames.push({ t: Date.parse(s.end), pos: [s.lat, s.lon] })
  }
  return frames.sort((a, b) => a.t - b.t)
}

export function positionAt(timeline: Keyframe[], time: number): LatLng | null {
  if (timeline.length === 0) return null
  if (time < timeline[0].t || time > timeline[timeline.length - 1].t) return null
  for (let i = 1; i < timeline.length; i++) {
    const b = timeline[i]
    if (time <= b.t) {
      const a = timeline[i - 1]
      const span = b.t - a.t
      const k = span === 0 ? 0 : (time - a.t) / span
      return [a.pos[0] + k * (b.pos[0] - a.pos[0]), a.pos[1] + k * (b.pos[1] - a.pos[1])]
    }
  }
  return timeline[timeline.length - 1].pos
}

export function downsample<T>(points: T[], max: number): T[] {
  if (points.length <= max) return points
  const step = (points.length - 1) / (max - 1)
  return Array.from({ length: max }, (_, i) => points[Math.round(i * step)])
}
