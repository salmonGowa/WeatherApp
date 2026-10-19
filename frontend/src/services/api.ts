import axios, { AxiosError } from 'axios'
import apiRoutes from '../../constants/apiRoutes'
import type { HeatmapResponse, LatLng, Place, PlanRequest, PlanResponse } from '../types'

const api = axios.create({
  baseURL: apiRoutes.BASE_URL,
  timeout: 180_000,
  headers: { 'Content-Type': 'application/json' },
})


export function errorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    if (!err.response) return 'Cannot reach the server. Check your connection and try again.'
    const data = err.response.data as Record<string, unknown> | undefined
    if (data && typeof data.detail === 'string') return data.detail
    if (data && typeof data === 'object') {
      const first = Object.entries(data)[0]
      if (first) {
        const [field, msgs] = first
        const msg = Array.isArray(msgs) ? msgs[0] : typeof msgs === 'object' ? Object.values(msgs ?? {})[0] : msgs
        const text = Array.isArray(msg) ? msg[0] : String(msg)
        return field === 'non_field_errors' ? text : `${field.replace(/_/g, ' ')}: ${text}`
      }
    }
    return `Request failed (${err.response.status})`
  }
  return err instanceof Error ? err.message : 'Something went wrong'
}

export async function geocode(q: string, signal?: AbortSignal): Promise<Place[]> {
  const { data } = await api.get<{ results: Place[] }>(apiRoutes.GEOCODE, { params: { q }, signal })
  return data.results
}

export async function planTrip(body: PlanRequest): Promise<PlanResponse> {
  const { data } = await api.post<PlanResponse>(apiRoutes.PLAN, body)
  return data
}

export async function fetchHeatmap(body: {
  routes: LatLng[][]
  start: string
  load_lb: number
}): Promise<HeatmapResponse> {
  const { data } = await api.post<HeatmapResponse>(apiRoutes.HEATMAP, body)
  return data
}

export default api
