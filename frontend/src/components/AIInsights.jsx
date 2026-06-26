import axios from 'axios'
import React, { useEffect, useState } from 'react'

function AnomalyRow({ a }) {
  const isHigh = a.confidence > 0.8
  const rowCls = isHigh
    ? 'border-red-700/60 bg-red-900/20'
    : 'border-yellow-700/60 bg-yellow-900/10'
  const confCls = isHigh ? 'text-red-400' : 'text-yellow-400'

  return (
    <div className={`border rounded-lg px-4 py-3 flex items-center justify-between gap-4 ${rowCls}`}>
      <div className="min-w-0">
        <span className="font-mono text-sm text-gray-200">{a.device}</span>
        <span className="text-gray-600 mx-2">—</span>
        <span className="text-sm text-gray-300">{a.metric}</span>
        <span className="text-gray-600 mx-2">=</span>
        <span className="text-sm text-gray-200">
          {a.value != null ? Number(a.value).toFixed(2) : '—'}
        </span>
      </div>
      <div className="text-right flex-shrink-0">
        <p className={`text-sm font-semibold ${confCls}`}>
          {a.confidence != null ? `${(a.confidence * 100).toFixed(0)}%` : '—'} confidence
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {new Date(a.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  )
}

function DeviceStatusCard({ device, status, anomaliesForDevice }) {
  const count = anomaliesForDevice.length

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
      <div className="flex items-start justify-between mb-2 gap-2">
        <div className="min-w-0">
          <p className="font-medium text-gray-100 text-sm truncate">{device.name}</p>
          <p className="text-xs text-gray-500 font-mono">{device.ip}</p>
        </div>
        {status.learning ? (
          <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full flex-shrink-0">
            Learning
          </span>
        ) : (
          <span className="text-xs bg-green-900/50 text-green-400 border border-green-700/40 px-2 py-0.5 rounded-full flex-shrink-0">
            Model Ready
          </span>
        )}
      </div>

      {status.learning ? (
        <p className="text-xs text-gray-500 mt-2">
          Collecting baseline data — needs {100} data points
        </p>
      ) : (
        <div className="mt-2 space-y-1 text-xs text-gray-400">
          <p>Metrics: {status.metrics_monitored.join(', ') || '—'}</p>
          <p>
            Anomalies today:{' '}
            <span className={count > 0 ? 'text-yellow-400 font-medium' : ''}>
              {count}
            </span>
          </p>
        </div>
      )}
    </div>
  )
}

export default function AIInsights() {
  const [anomalies, setAnomalies] = useState([])
  const [deviceStatuses, setDeviceStatuses] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [devicesRes, anomaliesRes] = await Promise.all([
          axios.get('/api/devices'),
          axios.get('/api/anomalies'),
        ])
        setAnomalies(anomaliesRes.data)

        const statuses = await Promise.all(
          devicesRes.data.map(async (device) => {
            try {
              const res = await axios.get(
                `/api/devices/${encodeURIComponent(device.id)}/anomaly-status`
              )
              return { device, ...res.data }
            } catch {
              return { device, has_model: false, metrics_monitored: [], learning: true }
            }
          })
        )
        setDeviceStatuses(statuses)
      } catch (err) {
        console.error('Failed to fetch AI insights:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchAll()
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      {/* Anomaly Timeline */}
      <section className="mb-10">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Anomaly Timeline — Last 24h
        </h2>

        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : anomalies.length === 0 ? (
          <div className="bg-gray-800 border border-gray-700 rounded-xl px-5 py-10 text-center">
            <p className="text-green-400 font-medium">No anomalies detected in the last 24 hours</p>
            <p className="text-gray-500 text-sm mt-1">All monitored metrics within normal range</p>
          </div>
        ) : (
          <div className="space-y-2">
            {anomalies.map((a, i) => (
              <AnomalyRow key={i} a={a} />
            ))}
          </div>
        )}
      </section>

      {/* Device Learning Status */}
      <section>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Model Status per Device
        </h2>

        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {deviceStatuses.map(({ device, ...status }) => (
              <DeviceStatusCard
                key={device.id}
                device={device}
                status={status}
                anomaliesForDevice={anomalies.filter((a) => a.device === device.name)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
