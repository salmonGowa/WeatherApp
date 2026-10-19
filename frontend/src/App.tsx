import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import CheckpointList from './components/CheckpointList'
import HeatmapControls from './components/map/HeatmapControls'
import MapView from './components/map/MapView'
import RouteList from './components/RouteList'
import TripForm from './components/TripForm'
import { downsample } from './lib/timeline'
import { errorMessage, fetchHeatmap, planTrip } from './services/api'
import { spinner } from './lib/ui'
import type { HeatmapMetric, PlanRequest, PlanResponse } from './types'
import { Truck } from 'lucide-react'



const HEATMAP_POINTS_PER_ROUTE = 1500

function useElapsedSeconds(running: boolean) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!running) return
    const start = Date.now()
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => {
      clearInterval(id)
      setSeconds(0)
    }
  }, [running])
  return seconds
}

export default function App() {
  const [plan, setPlan] = useState<PlanResponse | null>(null)
  const [planId, setPlanId] = useState(0)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [focus, setFocus] = useState<{ routeId: string; index: number } | null>(null)
  const [heatVisible, setHeatVisible] = useState(true)
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [hour, setHour] = useState(0)

  const planMutation = useMutation({
    mutationFn: (req: PlanRequest) => planTrip(req),
    onSuccess: (data) => {
      setPlan(data)
      setPlanId((n) => n + 1)
      setSelectedRouteId(data.recommendation.route_id)
      setFocus(null)
      setHour(0)
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  const heatmapQuery = useQuery({
   
    queryKey: ['heatmap', planId],
    enabled: plan !== null,
    staleTime: Infinity,
    retry: 1,
    queryFn: () =>
      fetchHeatmap({
        routes: plan!.routes.map((r) => downsample(r.geometry, HEATMAP_POINTS_PER_ROUTE)),
        start: plan!.departure,
        load_lb: plan!.load_lb,
      }),
  })

  const elapsed = useElapsedSeconds(planMutation.isPending)
  const selectedRoute = plan?.routes.find((r) => r.id === selectedRouteId) ?? null
  const heatmap = heatmapQuery.data ?? null
  const arrivalHour =
    heatmap && selectedRoute ? (Date.parse(selectedRoute.arrival) - Date.parse(heatmap.start)) / 3_600_000 : null

  const selectRoute = useCallback((id: string) => setSelectedRouteId(id), [])
  const focusCheckpoint = useCallback(
    (index: number) => selectedRouteId && setFocus({ routeId: selectedRouteId, index }),
    [selectedRouteId],
  )

  return (
    
    <div className="grid grid-cols-1 grid-rows-[70vh_auto] min-[860px]:h-full min-[860px]:grid-cols-[410px_1fr] min-[860px]:grid-rows-1">
      <aside className="order-2 flex flex-col gap-4 bg-panel px-4.5 pt-4.5 pb-7 min-[860px]:order-1 min-[860px]:overflow-y-auto min-[860px]:border-r min-[860px]:border-line">
        <header className="flex items-center gap-3">
          <span
            className="grid size-10 flex-none place-items-center rounded-[10px] bg-accent text-[22px] text-accent-ink"
            aria-hidden
          >
            <Truck />
          </span>
          <div>
            <h1 className="text-[17px]/tight font-bold">Weather-Aware Truck Routing</h1>
            <p className="mt-0.5 text-[12.5px] text-muted">
              Choose the safest route for the load, departure time and forecast.
            </p>
          </div>
        </header>

        <TripForm loading={planMutation.isPending} onSubmit={(req) => planMutation.mutate(req)} />

        {plan ? (
          <>
            <RouteList plan={plan} selectedRouteId={selectedRouteId} onSelect={selectRoute} />
            {selectedRoute && <CheckpointList route={selectedRoute} onFocus={focusCheckpoint} />}
            <p className="text-[11.5px] text-muted">
              ETAs assume trucks are capped at {plan.truck_max_speed_mph} mph
              {plan.hos_applied ? ' and include FMCSA hours-of-service breaks' : ''}. Each checkpoint's forecast is
              taken at the truck's ETA there.
            </p>
          </>
        ) : (
          !planMutation.isPending && (
            <section className="rounded-[10px] border border-dashed border-line p-3.5">
              <h2 className="text-sm font-bold">How routes are ranked</h2>
              <ol className="my-2 list-decimal pl-5">
                <li>Fewest Severe miles (No Travel miles count first)</li>
                <li>Fewest High miles</li>
                <li>Lowest average risk</li>
                <li>Shortest travel time</li>
              </ol>
              <p className="text-[12.5px] text-muted">
                Weather is sampled along each route every 10, 25 or 50 miles at the truck's estimated arrival
                time, and scored with the wind, rain and snow thresholds plus load-weight rules.
              </p>
            </section>
          )
        )}
      </aside>

      <main className="relative order-1 min-h-0 min-[860px]:order-2">
        <MapView
          plan={plan}
          selectedRouteId={selectedRouteId}
          onSelectRoute={selectRoute}
          focus={focus}
          heatmap={heatmap}
          heatmapVisible={heatVisible}
          metric={metric}
          hour={hour}
        />
        {planMutation.isPending && (
          <div
            className="absolute top-4 left-1/2 z-1000 flex max-w-[calc(100%-32px)] -translate-x-1/2 items-center gap-3 rounded-[10px] bg-panel px-4 py-3 shadow-float"
            role="status"
          >
            <span className={spinner} aria-hidden />
            <div className="flex flex-col">
              <strong>Planning routes…</strong>
              <span className="text-[12.5px] text-muted">
                Fetching routes and forecasts at each checkpoint ETA · {elapsed}s
                {elapsed > 20 && <> · the free weather API can be slow, hang tight</>}
              </span>
            </div>
          </div>
        )}
        {plan && (
          <HeatmapControls
            heatmap={heatmap}
            loading={heatmapQuery.isFetching}
            error={heatmapQuery.error ? errorMessage(heatmapQuery.error) : null}
            visible={heatVisible}
            onVisibleChange={setHeatVisible}
            metric={metric}
            onMetricChange={setMetric}
            hour={hour}
            onHourChange={setHour}
            arrivalHour={arrivalHour}
          />
        )}
      </main>
    </div>
  )
}
