export type RiskLevel = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'
export type LatLng = [number, number]

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string
  load_lb: number
  interval_miles: 10 | 25 | 50
  apply_hos: boolean
}

export interface RiskFactor {
  condition: 'wind' | 'rain' | 'snow'
  value: number
  unit: string
  level: RiskLevel
  load_adjusted: boolean
}

export interface Checkpoint {
  index: number
  mile: number
  lat: number
  lon: number
  eta: string
  covers: [number, number]
  weather: { wind_mph: number; gust_mph: number; rain_in_hr: number; snow_in_hr: number }
  risk: { level: RiskLevel; score: number; drivers: string[]; factors: RiskFactor[] }
}

export interface Stop {
  kind: 'break' | 'rest'
  lat: number
  lon: number
  mile: number
  start: string
  end: string
}

export interface RouteRisk {
  miles_by_level: Record<RiskLevel, number>
  total_miles: number
  average_risk: number
  max_level: RiskLevel
}

export interface PlannedRoute {
  id: string
  name: string
  summary: string
  synthesized: boolean
  distance_miles: number
  drive_hours: number
  duration_hours: number
  departure: string
  arrival: string
  geometry: LatLng[]
  segments: { level: RiskLevel; coords: LatLng[] }[]
  stops: Stop[]
  risk: RouteRisk
  checkpoints: Checkpoint[]
  recommended: boolean
  rank: number
}

export type Criterion = 'no_travel_miles' | 'severe_miles' | 'high_miles' | 'average_risk' | 'duration_hours' | 'tie'

export interface Recommendation {
  route_id: string
  ranking: string[]
  comparisons: { route_id: string; criterion: Criterion; phrase: string; best?: number; other?: number }[]
  warning: string | null
}

export interface PlanResponse {
  departure: string
  load_lb: number
  interval_miles: number
  hos_applied: boolean
  truck_max_speed_mph: number
  routes: PlannedRoute[]
  recommendation: Recommendation
}

export type HeatmapMetric = 'risk' | 'wind' | 'rain' | 'snow'

export interface HeatmapResponse {
  start: string
  hours: number
  corridor_miles: number
  grid: {
    cols: number
    rows: number
    bounds: { north: number; south: number; west: number; east: number }
    cells: number[]
    cell_km: number
  }
  series: Record<HeatmapMetric, number[][]> 
}
