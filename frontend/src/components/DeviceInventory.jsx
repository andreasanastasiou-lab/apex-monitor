import axios from 'axios'
import React, { useCallback, useEffect, useState } from 'react'
import AddDeviceModal from './AddDeviceModal'
import EditDeviceModal from './EditDeviceModal'

function StatusDot({ name, statusMap }) {
  const s = statusMap[name]
  if (!s) return <span className="w-2 h-2 rounded-full bg-gray-600 flex-shrink-0 inline-block" title="Unknown" />
  return (
    <span
      className={`w-2 h-2 rounded-full flex-shrink-0 inline-block ${s.is_alive ? 'bg-green-400' : 'bg-red-500'}`}
      title={s.is_alive ? `Online — ${s.latency_ms?.toFixed(1) ?? '?'} ms` : 'Offline'}
    />
  )
}

function TypeBadge({ type }) {
  const map = {
    workstation:    'text-blue-400 bg-blue-900/30',
    server:         'text-purple-400 bg-purple-900/30',
    network_device: 'text-amber-400 bg-amber-900/30',
    printer:        'text-gray-400 bg-gray-700',
  }
  const cls = map[type] || 'text-gray-400 bg-gray-800'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${cls}`}>
      {(type || 'unknown').replace(/_/g, ' ')}
    </span>
  )
}

function MonitorTags({ monitors }) {
  if (!monitors?.length) return null
  const labels = { icmp: 'ICMP', port_check: 'Ports', snmp: 'SNMP', ssh: 'SSH' }
  return (
    <span className="flex gap-1 flex-wrap">
      {monitors.map(m => (
        <span key={m} className="px-1.5 py-0.5 rounded text-xs bg-gray-800 text-gray-400">
          {labels[m] || m}
        </span>
      ))}
    </span>
  )
}

export default function DeviceInventory() {
  const [groups, setGroups]       = useState({})
  const [total, setTotal]         = useState(0)
  const [statusMap, setStatusMap] = useState({})
  const [collapsed, setCollapsed] = useState({})
  const [loading, setLoading]     = useState(true)
  const [showAdd, setShowAdd]     = useState(false)
  const [editDevice, setEditDevice] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)

  const fetchInventory = useCallback(() => {
    axios.get('/api/devices/inventory')
      .then(r => {
        setGroups(r.data.groups || {})
        setTotal(r.data.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchInventory() }, [fetchInventory])

  useEffect(() => {
    const fetchStatus = () => {
      axios.get('/api/devices')
        .then(r => {
          const map = {}
          for (const d of (r.data || [])) map[d.name] = d
          setStatusMap(map)
        })
        .catch(console.error)
    }
    fetchStatus()
    const id = setInterval(fetchStatus, 30_000)
    return () => clearInterval(id)
  }, [])

  const handleDelete = async (name) => {
    try {
      await axios.delete(`/api/devices/inventory/${encodeURIComponent(name)}`)
      fetchInventory()
    } catch (err) {
      console.error('Delete failed', err)
    } finally {
      setConfirmDelete(null)
    }
  }

  const toggleGroup = (g) => setCollapsed(c => ({ ...c, [g]: !c[g] }))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-gray-500 text-sm">Loading inventory…</span>
      </div>
    )
  }

  const groupNames = Object.keys(groups).sort()

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">Device Inventory</h1>
          <p className="text-xs text-gray-500 mt-0.5">{total} device{total !== 1 ? 's' : ''} registered</p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
        >
          <span className="text-base leading-none">+</span>
          Add Device
        </button>
      </div>

      {/* Groups */}
      {groupNames.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
          <p className="text-gray-500 text-sm">No devices in inventory.</p>
          <p className="text-gray-600 text-xs mt-1">Click "Add Device" to register one, or trigger migration from config.yaml.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {groupNames.map(groupName => {
            const devices = groups[groupName] || []
            const isCollapsed = !!collapsed[groupName]
            return (
              <div key={groupName} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                {/* Group header */}
                <button
                  onClick={() => toggleGroup(groupName)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-200">{groupName}</span>
                    <span className="px-2 py-0.5 rounded-full text-xs bg-gray-800 text-gray-400">
                      {devices.length}
                    </span>
                  </div>
                  <span className={`text-gray-500 text-xs transition-transform ${isCollapsed ? '' : 'rotate-180'}`}>
                    ▲
                  </span>
                </button>

                {/* Device rows */}
                {!isCollapsed && (
                  <div className="border-t border-gray-800 divide-y divide-gray-800">
                    {devices.map(device => (
                      <DeviceRow
                        key={device.name}
                        device={device}
                        statusMap={statusMap}
                        onEdit={() => setEditDevice(device)}
                        onDelete={() => setConfirmDelete(device.name)}
                        confirmDelete={confirmDelete === device.name}
                        onConfirmDelete={() => handleDelete(device.name)}
                        onCancelDelete={() => setConfirmDelete(null)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {showAdd && (
        <AddDeviceModal
          onClose={() => setShowAdd(false)}
          onAdded={() => { setShowAdd(false); fetchInventory() }}
        />
      )}

      {editDevice && (
        <EditDeviceModal
          device={editDevice}
          onClose={() => setEditDevice(null)}
          onUpdated={() => { setEditDevice(null); fetchInventory() }}
        />
      )}
    </div>
  )
}

function DeviceRow({ device, statusMap, onEdit, onDelete, confirmDelete, onConfirmDelete, onCancelDelete }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/30 transition-colors">
      {/* Status */}
      <StatusDot name={device.name} statusMap={statusMap} />

      {/* Name + IP */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-200 truncate">{device.name}</span>
          <span className="text-xs text-gray-500 font-mono">{device.ip}</span>
          <TypeBadge type={device.type} />
        </div>
        <div className="flex items-center gap-3 mt-0.5 flex-wrap">
          {device.location && (
            <span className="text-xs text-gray-500">📍 {device.location}</span>
          )}
          {device.owner && (
            <span className="text-xs text-gray-500">👤 {device.owner}</span>
          )}
          <MonitorTags monitors={device.monitors} />
          {device.ports?.length > 0 && (
            <span className="text-xs text-gray-600">
              ports: {device.ports.join(', ')}
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {confirmDelete ? (
          <>
            <span className="text-xs text-red-400">Delete?</span>
            <button onClick={onConfirmDelete}
              className="px-2 py-1 text-xs bg-red-600 hover:bg-red-500 text-white rounded transition-colors">
              Yes
            </button>
            <button onClick={onCancelDelete}
              className="px-2 py-1 text-xs border border-gray-600 text-gray-400 hover:text-gray-200 rounded transition-colors">
              No
            </button>
          </>
        ) : (
          <>
            <button onClick={onEdit}
              className="px-2.5 py-1 text-xs border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-gray-200 rounded transition-colors">
              Edit
            </button>
            <button onClick={onDelete}
              className="px-2.5 py-1 text-xs border border-gray-700 hover:border-red-700 text-gray-500 hover:text-red-400 rounded transition-colors">
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  )
}
