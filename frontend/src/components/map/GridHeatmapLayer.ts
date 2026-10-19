import L from 'leaflet'
import { colorAt, RAMPS } from '../../lib/colorRamp'
import type { HeatmapMetric, HeatmapResponse } from '../../types'

export class GridHeatmapLayer extends L.ImageOverlay {
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  private image: ImageData
  private data: HeatmapResponse

  constructor(data: HeatmapResponse, options?: L.ImageOverlayOptions) {
    const { north, south, east, west } = data.grid.bounds
    const canvas = document.createElement('canvas')
    canvas.width = data.grid.cols
    canvas.height = data.grid.rows
    
    super(canvas as unknown as string, L.latLngBounds([south, west], [north, east]), {
      interactive: false,
      ...options,
    })
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')!
    this.image = this.ctx.createImageData(canvas.width, canvas.height)
    this.data = data
  }

  _initImage() {
    const self = this as unknown as { _image: HTMLElement; _zoomAnimated: boolean }
    self._image = this.canvas
    L.DomUtil.addClass(this.canvas, 'leaflet-image-layer')
    L.DomUtil.addClass(this.canvas, 'grid-heatmap')
    if (self._zoomAnimated) L.DomUtil.addClass(this.canvas, 'leaflet-zoom-animated')
  }

  draw(metric: HeatmapMetric, hour: number) {
    const { cells } = this.data.grid
    const series = this.data.series[metric]
    const maxHour = this.data.hours
    const h0 = Math.max(0, Math.min(maxHour, Math.floor(hour)))
    const h1 = Math.min(maxHour, h0 + 1)
    const t = Math.max(0, Math.min(1, hour - h0))
    const { stops } = RAMPS[metric]
    const px = this.image.data
    px.fill(0)
    for (let i = 0; i < cells.length; i++) {
      const row = series[i]
      const value = row[h0] + t * (row[h1] - row[h0])
      const [r, g, b, a] = colorAt(stops, value)
      const o = cells[i] * 4
      px[o] = r
      px[o + 1] = g
      px[o + 2] = b
      px[o + 3] = a
    }
    this.ctx.putImageData(this.image, 0, 0)
  }
}
