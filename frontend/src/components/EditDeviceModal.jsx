import axios from 'axios'
import React, { useState } from 'react'

const TYPES = ['workstation', 'server', 'network_device', 'printer']
const GROUPS = ['Workstations', 'Servers', 'Network Devices', 'Printers']

function isValidIp(ip) {
  return /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip) &&
    ip.split('.').every(n => Number(n) >= 0 && Number(n) <= 255)
}

export default function EditDeviceModal({ device, onClose, onUpdated }) {
  const [form, setForm] = useState({
    ip: device.ip || '',
    type: device.type || 'workstation',
    group_name: device.group_name || '',
    location: device.location || '',
    owner: device.owner || '',
    notes: device.notes || '',
    monitors: device.monitors || ['icmp'],
    ports: (device.ports || []).join(', '),
  })
  const [error, setError]   = useState(null)
  const [loading, setLoading] = useState(false)

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const toggleMonitor = (m) => setForm(f => ({
    ...f,
    monitors: f.monitors.includes(m)
      ? f.monitors.filter(x => x !== m)
      : [...f.monitors, m],
  }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (!isValidIp(form.ip)) { setError('Enter a valid IPv4 address.'); return }

    const ports = form.ports
      .split(',')
      .map(s => parseInt(s.trim(), 10))
      .filter(n => !isNaN(n) && n > 0 && n <= 65535)

    setLoading(true)
    try {
      await axios.put(`/api/devices/inventory/${encodeURIComponent(device.name)}`, {
        ip: form.ip.trim(),
        type: form.type,
        group_name: form.group_name || null,
        location: form.location.trim() || null,
        owner: form.owner.trim() || null,
        notes: form.notes.trim() || null,
        monitors: form.monitors,
        ports,
      })
      onUpdated()
      onClose()
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(detail || 'Failed to update device.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Edit Device</h2>
            <p className="text-xs text-gray-500 mt-0.5">{device.name}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="IP Address *">
              <input required value={form.ip} onChange={set('ip')}
                className={inputCls} placeholder="192.168.1.10" />
            </Field>
            <Field label="Type">
              <select value={form.type} onChange={set('type')} className={inputCls}>
                {TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Group">
              <select value={form.group_name} onChange={set('group_name')} className={inputCls}>
                <option value="">None</option>
                {GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Location">
              <input value={form.location} onChange={set('location')}
                className={inputCls} placeholder="e.g. Office A" />
            </Field>
          </div>

          <Field label="Owner">
            <input value={form.owner} onChange={set('owner')}
              className={inputCls} placeholder="e.g. IT Team" />
          </Field>

          <Field label="Notes">
            <textarea value={form.notes} onChange={set('notes')} rows={2}
              className={inputCls + ' resize-none'} placeholder="Optional notes" />
          </Field>

          <Field label="Monitoring">
            <div className="flex gap-4 pt-1">
              {[['icmp', 'ICMP (Ping)'], ['port_check', 'Port Check']].map(([val, label]) => (
                <label key={val} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.monitors.includes(val)}
                    onChange={() => toggleMonitor(val)}
                    className="accent-blue-500"
                  />
                  {label}
                </label>
              ))}
            </div>
          </Field>

          {form.monitors.includes('port_check') && (
            <Field label="Ports (comma-separated)">
              <input value={form.ports} onChange={set('ports')}
                className={inputCls} placeholder="e.g. 22, 80, 443, 3389" />
            </Field>
          )}

          {error && (
            <div className="bg-red-900/30 border border-red-700/50 text-red-300 text-xs rounded-lg px-3 py-2.5">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 border border-gray-700 hover:border-gray-500 rounded-lg transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg transition-colors">
              {loading ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1.5">{label}</label>
      {children}
    </div>
  )
}

const inputCls = 'w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 transition-colors'
