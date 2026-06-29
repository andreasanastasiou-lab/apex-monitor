import axios from 'axios'
import React, { useEffect, useState } from 'react'

const RANGES = ['1h', '6h', '24h', '7d']
const DEVICE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

// ── SVG line chart ────────────────────────────────────────────────────────

function SvgLineChart({ series = [], baseline = null, height = 200 }) {
  const W = 600
  const PAD = { top: 10, right: 18, bottom: 36, left: 50 }
  const CW = W - PAD.left - PAD.right
  const CH = height - PAD.top - PAD.bottom

  const allPts = series
    .flatMap((s) => s.data || [])
    .filter((d) => d != null && d.value != null && isFinite(parseFloat(d.value)))

  if (allPts.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-gray-800/40 rounded-lg text-sm text-gray-500"
        style={{ height }}
      >
        No data available for this period
      </div>
    )
  }

  const allVals = allPts.map((d) => parseFloat(d.value))
  const rawMin = Math.min(...allVals, baseline ?? Infinity)
  const rawMax = Math.max(...allVals, baseline ?? -Infinity)
  const pad = (rawMax - rawMin) * 0.12 || 5
  const vMin = rawMin - pad
  const vMax = rawMax + pad
  const vRange = vMax - vMin

  const allMs = allPts.map((d) => new Date(d.timestamp).getTime()).filter((t) => !isNaN(t))
  const tMin = Math.min(...allMs)
  const tMax = Math.max(...allMs)
  const tRange = tMax - tMin || 1

  const xS = (t) => ((new Date(t).getTime() - tMin) / tRange) * CW
  const yS = (v) => CH - ((parseFloat(v) - vMin) / vRange) * CH

  const yTicks = Array.from({ length: 5 }, (_, i) => vMin + (vRange * i) / 4)
  const xTicks = allMs.length > 1 ? [tMin, (tMin + tMax) / 2, tMax] : [tMin]

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" style={{ display: 'block', height }}>
        <g transform={`translate(${PAD.left},${PAD.top})`}>
          {/* Grid + Y labels */}
          {yTicks.map((v, i) => (
            <g key={i}>
              <line x1={0} y1={yS(v).toFixed(1)} x2={CW} y2={yS(v).toFixed(1)} stroke="#1f2937" strokeWidth="1" />
              <text x={-6} y={yS(v) + 4} textAnchor="end" fill="#6b7280" fontSize="10">
                {v.toFixed(0)}
              </text>
            </g>
          ))}

          {/* X labels */}
          {xTicks.map((t, i) => (
            <text key={i} x={xS(t).toFixed(1)} y={CH + 22} textAnchor="middle" fill="#6b7280" fontSize="10">
              {new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </text>
          ))}

          {/* Axes */}
          <line x1={0} y1={0} x2={0} y2={CH} stroke="#374151" strokeWidth="1" />
          <line x1={0} y1={CH} x2={CW} y2={CH} stroke="#374151" strokeWidth="1" />

          {/* Baseline */}
          {baseline != null && (
            <line
              x1={0} y1={yS(baseline).toFixed(1)} x2={CW} y2={yS(baseline).toFixed(1)}
              stroke="#6b7280" strokeWidth="1.5" strokeDasharray="5,3"
            />
          )}

          {/* Series paths */}
          {series.map((s, si) => {
            const pts = (s.data || []).filter(
              (d) => d != null && d.value != null && isFinite(parseFloat(d.value))
            )
            if (pts.length === 0) return null
            const d = pts
              .map((p, i) => `${i === 0 ? 'M' : 'L'}${xS(p.timestamp).toFixed(1)},${yS(p.value).toFixed(1)}`)
              .join(' ')
            return (
              <path
                key={si}
                d={d}
                fill="none"
                stroke={s.color || '#3b82f6'}
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )
          })}
        </g>
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 mt-2">
        {series.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className="w-5 h-0 border-t-2" style={{ borderColor: s.color || '#3b82f6' }} />
            <span className="text-xs text-gray-400">{s.label}</span>
          </div>
        ))}
        {baseline != null && (
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-0 border-t-2 border-dashed border-gray-500" />
            <span className="text-xs text-gray-400">7-day baseline</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Summary stat card ─────────────────────────────────────────────────────

function StatCard({ label, value, unit = '', color = 'text-gray-100' }) {
  const display = value != null ? `${value}${unit}` : '—'
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{display}</p>
    </div>
  )
}

function latencyColor(ms) {
  if (ms == null) return 'text-gray-400'
  if (ms <= 50)  return 'text-green-400'
  if (ms <= 100) return 'text-yellow-400'
  return 'text-red-400'
}

function uptimeColor(pct) {
  if (pct == null) return 'text-gray-400'
  if (pct >= 99) return 'text-green-400'
  if (pct >= 95) return 'text-yellow-400'
  return 'text-red-400'
}

function countColor(n) {
  return n > 0 ? 'text-yellow-400' : 'text-green-400'
}

function deviationStatus(pct) {
  if (pct == null) return { label: 'No Data', cls: 'text-gray-400 bg-gray-800 border-gray-700' }
  const abs = Math.abs(pct)
  if (abs > 50) return { label: 'Severely Degraded', cls: 'text-red-400 bg-red-900/30 border-red-700/40' }
  if (abs > 20) return { label: 'Degraded',          cls: 'text-yellow-400 bg-yellow-900/30 border-yellow-700/40' }
  return           { label: 'Normal',                cls: 'text-green-400 bg-green-900/30 border-green-700/40' }
}

// ── Section wrapper ───────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div className="mb-8">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function DiagnosticView({ device, onClose }) {
  const [range, setRange] = useState('6h')
  const [data, setData] = useState(null)
  const [corrData, setCorrData] = useState(null)
  const [loading, setLoading] = useState(true)

  // ESC to close
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Fetch on open / range change
  useEffect(() => {
    if (!device) return
    setLoading(true)
    Promise.all([
      axios.get(`/api/diagnostic/${encodeURIComponent(device.id)}?range=${range}`),
      axios.get(`/api/diagnostic/correlation?range=${range}`),
    ])
      .then(([diagRes, corrRes]) => {
        setData(diagRes.data)
        setCorrData(corrRes.data)
      })
      .catch((err) => console.error('Diagnostic fetch failed:', err))
      .finally(() => setLoading(false))
  }, [device?.id, range])

  const handleExport = () => {
    const link = document.createElement('a')
    link.href = `/api/diagnostic/${encodeURIComponent(device.id)}/report?range=${range}`
    link.setAttribute('download', '')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  if (!device) return null

  const s = data?.summary ?? {}
  const bc = data?.baseline_comparison ?? {}
  const bcStatus = deviationStatus(bc.deviation_pct)

  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 overflow-y-auto"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="max-w-6xl mx-auto my-8 px-4 pb-12">

        {/* ── Header ──────────────────────────────────────── */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white">{device.name}</h2>
            <p className="text-sm text-gray-400 font-mono mt-0.5">{device.ip}</p>
            <p className="text-xs text-gray-600 mt-1">Press Esc or click outside to close</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Range selector */}
            <div className="flex gap-1">
              {RANGES.map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                    range === r
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:text-white border border-gray-700'
                  }`}
                >
                  {r.toUpperCase()}
                </button>
              ))}
            </div>
            <button
              onClick={onClose}
              className="ml-2 p-1.5 text-gray-500 hover:text-white transition-colors"
              aria-label="Close"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {loading ? (
          <div className="bg-gray-900 border border-gray-700 rounded-xl flex items-center justify-center h-64 text-sm text-gray-500">
            Loading diagnostic data…
          </div>
        ) : (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-0">

            {/* ── Section 1: Summary cards ──────────────────── */}
            <Section title="Summary">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <StatCard label="Avg Latency"   value={s.avg_latency_ms}  unit=" ms" color={latencyColor(s.avg_latency_ms)} />
                <StatCard label="Max Latency"   value={s.max_latency_ms}  unit=" ms" color={latencyColor(s.max_latency_ms)} />
                <StatCard label="Uptime"        value={s.uptime_pct}      unit="%"   color={uptimeColor(s.uptime_pct)} />
                <StatCard label="Packet Loss"   value={s.packet_loss_avg} unit="%"   color={s.packet_loss_avg > 0 ? 'text-yellow-400' : 'text-gray-400'} />
                <StatCard label="Anomalies"     value={s.anomalies_count ?? 0}       color={countColor(s.anomalies_count)} />
                <StatCard label="Alerts"        value={s.alerts_count ?? 0}          color={countColor(s.alerts_count)} />
              </div>
            </Section>

            {/* ── Section 2: Latency chart ───────────────────── */}
            <Section title={`Latency Timeline — Last ${range}`}>
              <div className="bg-gray-800/50 rounded-xl p-4">
                <SvgLineChart
                  series={[{ label: 'Actual latency', color: '#3b82f6', data: data?.latency_timeline ?? [] }]}
                  baseline={bc.baseline_avg_latency}
                  height={220}
                />
              </div>
            </Section>

            {/* ── Section 3: Baseline comparison ────────────── */}
            <Section title="Baseline Comparison (7-Day)">
              <div className={`border rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 ${bcStatus.cls}`}>
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Current Avg</p>
                  <p className="text-lg font-bold text-gray-100">
                    {bc.current_avg_latency != null ? `${bc.current_avg_latency} ms` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Baseline Avg</p>
                  <p className="text-lg font-bold text-gray-100">
                    {bc.baseline_avg_latency != null ? `${bc.baseline_avg_latency} ms` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Deviation</p>
                  <p className="text-lg font-bold text-gray-100">
                    {bc.deviation_pct != null ? `${bc.deviation_pct > 0 ? '+' : ''}${bc.deviation_pct}%` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-0.5">Status</p>
                  <p className={`text-lg font-bold ${bcStatus.cls.split(' ')[0]}`}>{bcStatus.label}</p>
                </div>
              </div>
            </Section>

            {/* ── Section 4: Multi-device correlation ──────── */}
            <Section title="Network-Wide Latency — Are Other Devices Affected?">
              <div className="bg-gray-800/50 rounded-xl p-4">
                {corrData?.devices?.length > 0 ? (
                  <SvgLineChart
                    series={(corrData.devices ?? []).map((d, i) => ({
                      label: d.device_name,
                      color: DEVICE_COLORS[i % DEVICE_COLORS.length],
                      data: d.latency_timeline,
                    }))}
                    height={220}
                  />
                ) : (
                  <p className="text-sm text-gray-500 py-8 text-center">No correlation data available</p>
                )}
              </div>
            </Section>

            {/* ── Section 5: Alerts & Anomalies ─────────────── */}
            <Section title="Alerts & Anomalies">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                {/* Alerts */}
                <div>
                  <p className="text-xs text-gray-500 mb-2">Alerts during period</p>
                  {data?.alerts_in_range?.length === 0 ? (
                    <div className="bg-green-900/20 border border-green-700/30 rounded-lg px-4 py-3 text-xs text-green-400">
                      None during this period
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {(data?.alerts_in_range ?? []).map((a, i) => {
                        const isCrit = a.severity === 'CRITICAL'
                        return (
                          <div
                            key={i}
                            className={`rounded-lg px-3 py-2 border ${isCrit ? 'bg-red-900/20 border-red-700/40' : 'bg-yellow-900/10 border-yellow-700/30'}`}
                          >
                            <div className="flex items-start gap-2">
                              <span className={`mt-0.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${isCrit ? 'bg-red-400' : 'bg-yellow-400'}`} />
                              <div className="min-w-0">
                                <p className="text-xs text-gray-300 leading-snug">{a.message}</p>
                                <p className="text-xs text-gray-600 mt-0.5">
                                  {new Date(a.timestamp).toLocaleTimeString()}
                                </p>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Anomalies */}
                <div>
                  <p className="text-xs text-gray-500 mb-2">Anomalies during period</p>
                  {data?.anomalies_in_range?.length === 0 ? (
                    <div className="bg-green-900/20 border border-green-700/30 rounded-lg px-4 py-3 text-xs text-green-400">
                      None during this period
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {(data?.anomalies_in_range ?? []).map((a, i) => {
                        const isHigh = a.confidence > 0.8
                        return (
                          <div
                            key={i}
                            className={`rounded-lg px-3 py-2 border ${isHigh ? 'bg-red-900/20 border-red-700/40' : 'bg-yellow-900/10 border-yellow-700/30'}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="min-w-0">
                                <p className="text-xs text-gray-200 font-mono">{a.metric}</p>
                                <p className="text-xs text-gray-500 mt-0.5">
                                  {new Date(a.timestamp).toLocaleTimeString()}
                                </p>
                              </div>
                              <p className={`text-xs font-semibold flex-shrink-0 ${isHigh ? 'text-red-400' : 'text-yellow-400'}`}>
                                {a.confidence != null ? `${(a.confidence * 100).toFixed(0)}%` : '—'}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            </Section>

            {/* ── Section 6: Export ─────────────────────────── */}
            <div className="pt-2 flex justify-end">
              <button
                onClick={handleExport}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Export Report
              </button>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
