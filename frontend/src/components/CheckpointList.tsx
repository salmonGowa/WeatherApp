import { Scale } from 'lucide-react'
import { memo } from 'react'
import { formatTime } from '../lib/format'
import { RISK_COLOR, RISK_LABEL } from '../lib/risk'
import type { PlannedRoute } from '../types'

interface Props {
  route: PlannedRoute
  onFocus: (index: number) => void
}

const th = 'sticky -top-4.5 border-b border-line bg-panel p-1 text-left font-semibold text-muted'
const td = 'whitespace-nowrap border-b border-line p-1'

function CheckpointList({ route, onFocus }: Props) {
  return (
    <section>
      <h3 className="mb-1.5 text-sm font-bold">
        {route.name} checkpoints <span className="font-normal text-muted">({route.checkpoints.length})</span>
      </h3>
      <table className="w-full border-collapse text-[12.5px] tabular-nums">
        <thead>
          <tr>
            <th className={th}>Mile</th>
            <th className={th}>ETA</th>
            <th className={th} title="Sustained wind">
              Wind
            </th>
            <th className={th}>Rain</th>
            <th className={th}>Snow</th>
            <th className={th}>Risk</th>
          </tr>
        </thead>
        <tbody>
          {route.checkpoints.map((cp) => (
            <tr
              key={cp.index}
              className="cursor-pointer outline-none hover:bg-accent-soft focus:bg-accent-soft"
              onClick={() => onFocus(cp.index)}
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onFocus(cp.index)}
            >
              <td className={td}>{cp.mile.toFixed(0)}</td>
              <td className={td}>{formatTime(cp.eta)}</td>
              <td className={td}>{cp.weather.wind_mph.toFixed(0)}</td>
              <td className={td}>{cp.weather.rain_in_hr.toFixed(2)}</td>
              <td className={td}>{cp.weather.snow_in_hr.toFixed(2)}</td>
              <td className={td}>
                <span
                  className="mr-1.5 inline-block size-2.25 rounded-full"
                  style={{ background: RISK_COLOR[cp.risk.level] }}
                />
                {RISK_LABEL[cp.risk.level]}
                {cp.risk.factors.some((f) => f.load_adjusted && f.level === cp.risk.level) && (
                  <Scale
                    className="ml-1 inline size-3.5 align-[-2px] text-muted"
                    aria-label="Escalated by the load-weight rule"
                  >
                    <title>Escalated by the load-weight rule</title>
                  </Scale>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1.5 text-[11.5px] text-muted">
        Units: wind mph, rain and snow in/hr. Click a row to show it on the map.
      </p>
    </section>
  )
}

export default memo(CheckpointList)
