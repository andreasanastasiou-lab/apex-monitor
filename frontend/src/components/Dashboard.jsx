import axios from 'axios'
import React, { useEffect, useState } from 'react'
import DeviceCard from './DeviceCard'
import NotificationPanel from './NotificationPanel'

function StatCard({ label, value, cls }) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${cls}`}>{value}</p>
    </div>
  )
}

function SummaryBar({ devices }) {
  const up   = devices.filter((d) => d.status === 'UP').length
  const warn = devices.filter((d) => d.status === 'WARNING').length
  const down = devices.filter((d) => d.status === 'DOWN').length
  const lats = devices.map((d) => d.latency_ms).filter((l) => l != null)
  const avg  = lats.length ? (lats.reduce((a, b) => a + b, 0) / lats.length).toFixed(1) : null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      <StatCard label="Total"       value={devices.length}               cls="text-gray-200" />
      <StatCard label="Up"          value={up}                           cls="text-green-400" />
      <StatCard label="Down / Warn" value={`${down} / ${warn}`}         cls="text-red-400" />
      <StatCard label="Avg Latency" value={avg != null ? `${avg} ms` : '—'} cls="text-blue-400" />
    </div>
  )
}

export default function Dashboard() {
  const [devices, setDevices]           = useState([])
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState(null)
  const [lastRefresh, setLastRefresh]   = useState(null)
  const [unreadCount, setUnreadCount]   = useState(0)
  const [panelOpen, setPanelOpen]       = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get('/api/devices')
        setDevices(res.data)
        setError(null)
        setLastRefresh(new Date())
      } catch (err) {
        setError('Could not reach backend — is uvicorn running?')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const res = await axios.get('/api/notifications/count')
        setUnreadCount(res.data.unread)
      } catch {
        // notification count is non-critical; ignore failures silently
      }
    }

    fetchCount()
    const id = setInterval(fetchCount, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <NotificationPanel isOpen={panelOpen} onClose={() => setPanelOpen(false)} />

      {/* Header */}
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Apex Monitor</h1>
          <p className="text-sm text-gray-400 mt-0.5">Network visibility dashboard</p>
        </div>
        <div className="flex items-center gap-4">
          {/* Notification bell */}
          <button
            onClick={() => setPanelOpen(true)}
            className="relative p-2 text-gray-400 hover:text-white transition-colors"
            aria-label="Open notifications"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-xs rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 font-medium leading-none">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* Last refresh */}
          <div className="text-right text-xs text-gray-500">
            {lastRefresh ? (
              <>
                <span>Last refresh</span>
                <br />
                <span className="font-mono text-gray-400">{lastRefresh.toLocaleTimeString()}</span>
              </>
            ) : (
              <span>Connecting…</span>
            )}
          </div>
        </div>
      </header>

      {/* Error state */}
      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6 text-sm">
          {error}
        </div>
      )}

      {/* Summary bar */}
      {!loading && !error && <SummaryBar devices={devices} />}

      {/* Device grid */}
      {loading ? (
        <div className="text-center py-20 text-gray-500 text-sm">Loading devices…</div>
      ) : devices.length === 0 && !error ? (
        <div className="text-center py-20 text-gray-500 text-sm">
          No devices found — check config.yaml
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {devices.map((device) => (
            <DeviceCard key={device.id} device={device} />
          ))}
        </div>
      )}
    </div>
  )
}
