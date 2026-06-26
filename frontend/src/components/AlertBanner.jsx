import React, { useEffect, useState } from 'react'
import axios from 'axios'

export default function AlertBanner() {
  const [alerts, setAlerts] = useState([])
  const [dismissedCount, setDismissedCount] = useState(null)

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get('/api/alerts')
        setAlerts(res.data)
      } catch (err) {
        console.error('Failed to fetch alerts:', err)
      }
    }
    fetch()
    const id = setInterval(fetch, 60_000)
    return () => clearInterval(id)
  }, [])

  if (alerts.length === 0 || dismissedCount === alerts.length) return null

  const hasCritical = alerts.some((a) => a.severity === 'critical')
  const bannerCls = hasCritical
    ? 'bg-red-900/80 border-red-600'
    : 'bg-yellow-800/80 border-yellow-500'
  const labelCls = hasCritical ? 'text-red-200' : 'text-yellow-200'

  return (
    <div className={`border-l-4 px-5 py-3 flex items-start justify-between gap-4 ${bannerCls}`}>
      <div>
        <p className={`font-semibold text-sm ${labelCls}`}>
          {hasCritical ? 'Critical alert' : 'Warning'} — {alerts.length} active event
          {alerts.length !== 1 ? 's' : ''}
        </p>
        <ul className="mt-1 space-y-0.5">
          {alerts.slice(0, 5).map((a, i) => (
            <li key={i} className="text-xs text-gray-300">
              <span className="font-mono">{a.device}</span>
              {' — '}
              {a.metric}
              {a.port != null ? ` (port ${a.port})` : ''}
              {' at '}
              {new Date(a.timestamp).toLocaleTimeString()}
            </li>
          ))}
          {alerts.length > 5 && (
            <li className="text-xs text-gray-400">…and {alerts.length - 5} more</li>
          )}
        </ul>
      </div>
      <button
        onClick={() => setDismissedCount(alerts.length)}
        className="text-gray-300 hover:text-white text-lg leading-none mt-0.5 flex-shrink-0"
        aria-label="Dismiss"
      >
        &times;
      </button>
    </div>
  )
}
