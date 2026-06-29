import axios from 'axios'
import React, { useState } from 'react'

const STATUS = {
  UP:      { badge: 'bg-green-500/20 text-green-400 border border-green-600/40', dot: 'bg-green-400' },
  WARNING: { badge: 'bg-yellow-500/20 text-yellow-400 border border-yellow-600/40', dot: 'bg-yellow-400' },
  DOWN:    { badge: 'bg-red-500/20 text-red-400 border border-red-600/40', dot: 'bg-red-400' },
}

export default function DeviceCard({ device, onInvestigate = () => {} }) {
  const [open, setOpen] = useState(false)
  const [metrics, setMetrics] = useState([])
  const [loading, setLoading] = useState(false)

  const toggle = async () => {
    if (open) { setOpen(false); return }
    setOpen(true)
    setLoading(true)
    try {
      const res = await axios.get(`/api/devices/${encodeURIComponent(device.id)}/metrics`)
      setMetrics(res.data)
    } catch {
      setMetrics([])
    } finally {
      setLoading(false)
    }
  }

  const style = STATUS[device.status] ?? STATUS.DOWN

  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-xl p-4 cursor-pointer
                 hover:border-gray-500 hover:bg-gray-750 transition-colors select-none"
      onClick={toggle}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-100 text-sm truncate">{device.name}</h3>
          <p className="text-gray-400 text-xs font-mono mt-0.5">{device.ip}</p>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${style.badge}`}>
          <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${style.dot}`} />
          {device.status}
        </span>
      </div>

      {/* Footer row */}
      <div className="flex items-center justify-between mt-3 text-xs text-gray-400">
        <span className="capitalize">{device.type}</span>
        <div className="flex items-center gap-2">
          <span>{device.latency_ms != null ? `${device.latency_ms} ms` : '—'}</span>
          <button
            onClick={(e) => { e.stopPropagation(); onInvestigate(device) }}
            className="px-2 py-0.5 text-xs text-blue-400 border border-blue-600/40 rounded hover:bg-blue-900/30 transition-colors"
          >
            Investigate
          </button>
        </div>
      </div>

      {/* Expandable metrics panel */}
      {open && (
        <div
          className="mt-4 pt-4 border-t border-gray-700"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="text-xs font-medium text-gray-400 mb-2">Latency — last 1h</p>
          {loading ? (
            <p className="text-xs text-gray-500">Loading…</p>
          ) : metrics.length === 0 ? (
            <p className="text-xs text-gray-500">No data in InfluxDB yet</p>
          ) : (
            <ul className="space-y-1 max-h-36 overflow-y-auto pr-1">
              {metrics.slice(-20).reverse().map((m, i) => (
                <li key={i} className="flex justify-between text-xs">
                  <span className="text-gray-500 font-mono">
                    {new Date(m.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="text-gray-300">
                    {m.value != null ? `${m.value} ms` : '—'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
