import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Flag, Truck } from 'lucide-react'
import { useEffect, useMemo, useRef, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { RISK_COLOR } from '../../lib/risk'
import { buildTimeline, positionAt } from '../../lib/timeline'
import type { HeatmapMetric, HeatmapResponse, PlanResponse } from '../../types'
import { GridHeatmapLayer } from './GridHeatmapLayer'
import { checkpointPopup, checkpointTooltip, stopTooltip } from './popups'

interface Props {
  plan: PlanResponse | null
  selectedRouteId: string | null
  onSelectRoute: (id: string) => void
  focus: { routeId: string; index: number } | null
  heatmap: HeatmapResponse | null
  heatmapVisible: boolean
  metric: HeatmapMetric
  hour: number
}

const US_CENTER: L.LatLngExpression = [39.5, -98.35]

const PIN_BASE =
  'grid place-items-center rounded-full border-2 border-white font-bold text-white shadow-[0_1px_4px_rgb(0_0_0/0.35)]'
const PIN = {
  truck: `${PIN_BASE} size-7.5 border-[#1b2733] bg-white text-base`,
  origin: `${PIN_BASE} size-4.5 border-4 bg-[#1b2733]`,
  destination: `${PIN_BASE} size-6 bg-[#0b6e8a] text-xs`,
  break: `${PIN_BASE} h-5 w-8.5 rounded-[10px] bg-[#495057] text-[10px]`,
  rest: `${PIN_BASE} h-5 w-8.5 rounded-[10px] bg-[#364fc7] text-[10px]`,
}


function toMarkup(node: ReactNode): string {
  const el = document.createElement('div')
  const root = createRoot(el)
  flushSync(() => root.render(node))
  const html = el.innerHTML
  root.unmount()
  return html
}

const TRUCK_SVG = toMarkup(<Truck size={16} color="#1b2733" strokeWidth={2.25} aria-hidden />)
const FLAG_SVG = toMarkup(<Flag size={12} color="#ffffff" strokeWidth={2.5} aria-hidden />)

function pinIcon(label: string, spanClass: string, size: [number, number] = [28, 28]) {
  return L.divIcon({
    className: 'pin',
    html: `<span class="${spanClass}">${label}</span>`,
    iconSize: size,
    iconAnchor: [size[0] / 2, size[1] / 2],
  })
}

export default function MapView({
  plan,
  selectedRouteId,
  onSelectRoute,
  focus,
  heatmap,
  heatmapVisible,
  metric,
  hour,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layersRef = useRef<{
    routes: L.LayerGroup
    checkpoints: L.LayerGroup
    markers: L.LayerGroup
    routeRenderer: L.Canvas
    checkpointRenderer: L.Canvas
    truck: L.Marker
  } | null>(null)
  const heatRef = useRef<GridHeatmapLayer | null>(null)
  const cpMarkersRef = useRef(new Map<string, L.CircleMarker>())

  // ---- map setup
  useEffect(() => {
    const map = L.map(containerRef.current!, { zoomControl: false, minZoom: 3 }).setView(US_CENTER, 4)
    L.control.zoom({ position: 'topright' }).addTo(map)
    L.control.scale({ position: 'bottomright', imperial: true, metric: false }).addTo(map)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Weather: <a href="https://open-meteo.com/">Open-Meteo</a> · Routing: <a href="https://project-osrm.org/">OSRM</a>',
      maxZoom: 19,
    }).addTo(map)

    // Pane order: heatmap < routes < checkpoints < markers
    map.createPane('heatmap').style.zIndex = '350'
    map.createPane('routes').style.zIndex = '420'
    map.createPane('checkpoints').style.zIndex = '440'

    layersRef.current = {
      routes: L.layerGroup().addTo(map),
      checkpoints: L.layerGroup().addTo(map),
      markers: L.layerGroup().addTo(map),
      routeRenderer: L.canvas({ pane: 'routes', tolerance: 6 }),
      checkpointRenderer: L.canvas({ pane: 'checkpoints', tolerance: 4 }),
      truck: L.marker([0, 0], { icon: pinIcon(TRUCK_SVG, PIN.truck), interactive: false, zIndexOffset: 1000 }),
    }
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      layersRef.current = null
      heatRef.current = null
    }
  }, [])

  // ---- fit to routes when a new plan arrives
  useEffect(() => {
    const map = mapRef.current
    if (!map || !plan) return
    const bounds = L.latLngBounds(plan.routes.flatMap((r) => r.geometry))
    map.fitBounds(bounds, { padding: [40, 40] })
  }, [plan])

  // ---- routes, checkpoints, stops 
  useEffect(() => {
    const layers = layersRef.current
    if (!layers) return
    layers.routes.clearLayers()
    layers.checkpoints.clearLayers()
    layers.markers.clearLayers()
    cpMarkersRef.current.clear()
    if (!plan) return

    const selected = plan.routes.find((r) => r.id === selectedRouteId) ?? plan.routes[0]
    const others = plan.routes.filter((r) => r !== selected)

    // Unselected routes: muted, clickable.
    for (const route of others) {
      L.polyline(route.geometry, {
        renderer: layers.routeRenderer,
        color: '#5c6b7a',
        weight: 5,
        opacity: 0.55,
      })
        .bindTooltip(`${route.name}${route.recommended ? ' (recommended)' : ''} · click to select`, { sticky: true })
        .on('click', () => onSelectRoute(route.id))
        .addTo(layers.routes)
      for (const cp of route.checkpoints) {
        L.circleMarker([cp.lat, cp.lon], {
          renderer: layers.checkpointRenderer,
          radius: 3,
          weight: 1,
          color: '#fff',
          fillColor: RISK_COLOR[cp.risk.level],
          fillOpacity: 0.85,
        })
          .bindTooltip(checkpointTooltip(route, cp))
          .bindPopup(() => checkpointPopup(route, cp), { maxWidth: 320 })
          .addTo(layers.checkpoints)
      }
    }

    // Selected route: white casing + risk-coloured segments.
    L.polyline(selected.geometry, {
      renderer: layers.routeRenderer,
      color: '#fff',
      weight: 10,
      opacity: 0.95,
      interactive: false,
    }).addTo(layers.routes)
    for (const seg of selected.segments) {
      L.polyline(seg.coords, {
        renderer: layers.routeRenderer,
        color: RISK_COLOR[seg.level],
        weight: 6,
        opacity: 1,
        interactive: false,
      }).addTo(layers.routes)
    }
    for (const cp of selected.checkpoints) {
      const marker = L.circleMarker([cp.lat, cp.lon], {
        renderer: layers.checkpointRenderer,
        radius: 6,
        weight: 2,
        color: '#fff',
        fillColor: RISK_COLOR[cp.risk.level],
        fillOpacity: 1,
      })
        .bindTooltip(checkpointTooltip(selected, cp))
        .bindPopup(() => checkpointPopup(selected, cp), { maxWidth: 320 })
        .addTo(layers.checkpoints)
      cpMarkersRef.current.set(`${selected.id}:${cp.index}`, marker)
    }
    for (const stop of selected.stops) {
      L.marker([stop.lat, stop.lon], {
        icon: pinIcon(stop.kind === 'rest' ? '10h' : '30m', PIN[stop.kind], [34, 20]),
      })
        .bindTooltip(stopTooltip(stop))
        .addTo(layers.markers)
    }

    const first = selected.checkpoints[0]
    const last = selected.checkpoints[selected.checkpoints.length - 1]
    L.marker([first.lat, first.lon], { icon: pinIcon('', PIN.origin) })
      .bindTooltip('Origin')
      .addTo(layers.markers)
    L.marker([last.lat, last.lon], { icon: pinIcon(FLAG_SVG, PIN.destination) })
      .bindTooltip('Destination')
      .addTo(layers.markers)
  }, [plan, selectedRouteId, onSelectRoute])

  // focus a checkpoint from the sidebar
  useEffect(() => {
    const map = mapRef.current
    if (!map || !focus) return
    const marker = cpMarkersRef.current.get(`${focus.routeId}:${focus.index}`)
    if (!marker) return
    map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 8), { duration: 0.6 })
    marker.openPopup()
  }, [focus])

  //  heatmap layer
  useEffect(() => {
    const map = mapRef.current
    heatRef.current?.remove()
    heatRef.current = null
    if (!map || !heatmap) return
    heatRef.current = new GridHeatmapLayer(heatmap, { pane: 'heatmap' })
  }, [heatmap])

  useEffect(() => {
    const map = mapRef.current
    const layer = heatRef.current
    if (!map || !layer) return
    if (heatmapVisible && !map.hasLayer(layer)) layer.addTo(map)
    if (!heatmapVisible && map.hasLayer(layer)) layer.remove()
  }, [heatmap, heatmapVisible])

  useEffect(() => {
    heatRef.current?.draw(metric, hour)
  }, [heatmap, metric, hour])

  // truck position at the slider time 
  const selectedRoute = plan?.routes.find((r) => r.id === selectedRouteId) ?? plan?.routes[0]
  const timeline = useMemo(
    () => (selectedRoute ? buildTimeline(selectedRoute.checkpoints, selectedRoute.stops) : []),
    [selectedRoute],
  )
  useEffect(() => {
    const map = mapRef.current
    const truck = layersRef.current?.truck
    if (!map || !truck) return
    const pos = heatmap ? positionAt(timeline, Date.parse(heatmap.start) + hour * 3_600_000) : null
    if (pos && heatmapVisible) {
      truck.setLatLng(pos)
      if (!map.hasLayer(truck)) truck.addTo(map)
    } else if (map.hasLayer(truck)) {
      truck.remove()
    }
  }, [timeline, heatmap, heatmapVisible, hour])

  return <div ref={containerRef} className="absolute inset-0 bg-[#dfe5ea]" role="region" aria-label="Route map" />
}
