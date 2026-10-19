import type { RiskLevel } from '../types'

export const RISK_LEVELS: RiskLevel[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
}

export const RISK_COLOR: Record<RiskLevel, string> = {
  low: '#2f9e44',
  moderate: '#f2c200',
  high: '#f76707',
  severe: '#e03131',
  no_travel: '#862e9c',
}

export const CRITERION_LABEL: Record<string, string> = {
  no_travel_miles: 'No Travel miles',
  severe_miles: 'Severe miles',
  high_miles: 'High miles',
  average_risk: 'average risk',
  duration_hours: 'travel time',
}
