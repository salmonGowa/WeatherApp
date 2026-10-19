import { Check } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { geocode } from '../services/api'
import { fieldLabel, input, spinner } from '../lib/ui'
import type { Place } from '../types'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  placeholder?: string
}

const COORDS = /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/


function parseCoords(text: string): Place | null {
  const m = COORDS.exec(text)
  if (!m) return null
  const lat = Number(m[1])
  const lon = Number(m[2])
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
  return { label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`, lat, lon }
}

export default function LocationInput({ label, value, onChange, placeholder }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [loading, setLoading] = useState(false)
  const [prevValue, setPrevValue] = useState(value)
  if (value !== prevValue) {
    setPrevValue(value)
    if (value) setText(value.label)
  }

  const query = text.trim()
  const searchable = query.length >= 3 && query !== value?.label && !parseCoords(query)

  
  useEffect(() => {
    if (!searchable) return
    const ctrl = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const found = await geocode(query, ctrl.signal)
        setResults(found)
        setActive(0)
        setOpen(true)
      } catch {
        if (!ctrl.signal.aborted) setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => {
      clearTimeout(timer)
      ctrl.abort()
      setLoading(false)
    }
  }, [query, searchable])

  const choose = (place: Place) => {
    onChange(place)
    setText(place.label)
    setOpen(false)
    setResults([])
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const coords = parseCoords(text)
      if (coords) {
        e.preventDefault()
        choose(coords)
      } else if (open && results[active]) {
        e.preventDefault()
        choose(results[active])
      }
      return
    }
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (i + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (i - 1 + results.length) % results.length)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative flex min-w-0 flex-1 flex-col gap-1">
      <label htmlFor={id} className={fieldLabel}>
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type="text"
          className={`${input} pr-8`}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${id}-list`}
          placeholder={placeholder}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            if (value) onChange(null)
          }}
          onBlur={() => {
            const coords = parseCoords(text)
            if (coords && !value) choose(coords)
            setTimeout(() => setOpen(false), 150)
          }}
          onFocus={() => searchable && results.length > 0 && setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {loading && <span className={`${spinner} absolute top-2.5 right-2.5`} aria-hidden />}
        {value && !loading && (
          <Check
            className="absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-green-600"
            strokeWidth={3}
            aria-label="Location set"
          />
        )}
      </div>
      {open && searchable && results.length > 0 && (
        <ul
          className="absolute inset-x-0 top-full z-1000 mt-1 list-none rounded-lg border border-line bg-panel p-1 shadow-float"
          id={`${id}-list`}
          role="listbox"
        >
          {results.map((r, i) => (
            <li
              key={`${r.label}-${r.lat}`}
              role="option"
              aria-selected={i === active}
              className="cursor-pointer rounded-md px-2 py-1.75 aria-selected:bg-accent-soft"
              onMouseDown={(e) => {
                e.preventDefault()
                choose(r)
              }}
              onMouseEnter={() => setActive(i)}
            >
              {r.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
