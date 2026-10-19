import { ArrowUpDown } from 'lucide-react'
import { useState } from 'react'
import { toLocalInputValue } from '../lib/format'
import { checkbox, fieldLabel, hiddenRadio, input, segment, toggle } from '../lib/ui'
import type { Place, PlanRequest } from '../types'
import LocationInput from './LocationInput'

interface Props {
  loading: boolean
  onSubmit: (req: PlanRequest) => void
}

const EXAMPLES: { name: string; origin: Place; destination: Place }[] = [
  {
    name: 'Chicago --> Denver',
    origin: { label: 'Chicago, Illinois, United States', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Denver, Colorado, United States', lat: 39.7392, lon: -104.9903 },
  },
  {
    name: 'Dallas --> Atlanta',
    origin: { label: 'Dallas, Texas, United States', lat: 32.7767, lon: -96.797 },
    destination: { label: 'Atlanta, Georgia, United States', lat: 33.749, lon: -84.388 },
  },
  {
    name: 'Seattle --> Salt Lake City',
    origin: { label: 'Seattle, Washington, United States', lat: 47.6062, lon: -122.3321 },
    destination: { label: 'Salt Lake City, Utah, United States', lat: 40.7608, lon: -111.891 },
  },
]

function nextHour(): Date {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  return d
}

export default function TripForm({ loading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(() => toLocalInputValue(nextHour()))
  const [load, setLoad] = useState('35000')
  const [interval, setIntervalMiles] = useState<10 | 25 | 50>(25)
  const [hos, setHos] = useState(true)

  const loadLb = Number(load)
  const loadValid = load.trim() !== '' && Number.isFinite(loadLb) && loadLb >= 0 && loadLb <= 200_000
  const canSubmit = origin && destination && departure && loadValid && !loading

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lb: loadLb,
      interval_miles: interval,
      apply_hos: hos,
    })
  }

  return (
    <form className="relative flex flex-col gap-2.5" onSubmit={submit}>
      <LocationInput label="Origin" value={origin} onChange={setOrigin} placeholder="City, address or lat, lon" />
      <button
        type="button"
        className="absolute top-13 right-1.5 z-2 grid size-6.5 cursor-pointer place-items-center rounded-full border border-line bg-panel p-0"
        title="Swap origin and destination"
        aria-label="Swap origin and destination"
        onClick={() => {
          setOrigin(destination)
          setDestination(origin)
        }}
      >
        <ArrowUpDown className="size-3.5" aria-hidden />
      </button>
      <LocationInput
        label="Destination"
        value={destination}
        onChange={setDestination}
        placeholder="City, address or lat, lon"
      />

      <div className="flex gap-2.5">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <label htmlFor="departure" className={fieldLabel}>
            Departure
          </label>
          <input
            id="departure"
            className={input}
            type="datetime-local"
            value={departure}
            onChange={(e) => setDeparture(e.target.value)}
            required
          />
        </div>
        <div className="flex w-30 flex-none flex-col gap-1">
          <label htmlFor="load" className={fieldLabel}>
            Load (lb)
          </label>
          <input
            id="load"
            className={input}
            type="number"
            inputMode="numeric"
            min={0}
            max={200000}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            aria-invalid={!loadValid}
            required
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-2.5">
        <fieldset className="m-0 inline-flex flex-wrap border-0 p-0">
          <legend className={`${fieldLabel} mb-1`}>Weather sample every</legend>
          {([10, 25, 50] as const).map((mi) => (
            <label key={mi} className={segment()}>
              <input
                type="radio"
                name="interval"
                className={hiddenRadio}
                checked={interval === mi}
                onChange={() => setIntervalMiles(mi)}
              />
              {mi} mi
            </label>
          ))}
        </fieldset>
        <label className={toggle} title="Insert FMCSA 30-min breaks and 10-hr rests into ETAs">
          <input type="checkbox" className={checkbox} checked={hos} onChange={(e) => setHos(e.target.checked)} />
          HOS breaks
        </label>
      </div>

      <button
        type="submit"
        className="mt-1 h-10.5 cursor-pointer rounded-lg bg-accent font-semibold text-accent-ink disabled:cursor-not-allowed disabled:opacity-55"
        disabled={!canSubmit}
      >
        {loading ? 'Planning…' : 'Plan routes'}
      </button>

      <div className="flex flex-wrap gap-x-2.5 gap-y-1 text-[12.5px] text-muted">
        <span>Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.name}
            type="button"
            className="cursor-pointer text-accent underline underline-offset-2"
            onClick={() => {
              setOrigin(ex.origin)
              setDestination(ex.destination)
            }}
          >
            {ex.name}
          </button>
        ))}
      </div>
    </form>
  )
}
