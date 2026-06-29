import axios from 'axios'
import React, { useEffect, useState } from 'react'

const SEVERITY_STYLE = {
  CRITICAL: { dot: 'bg-red-500',    border: 'border-red-500',    bg: 'bg-red-900/20'    },
  WARNING:  { dot: 'bg-yellow-500', border: 'border-yellow-500', bg: 'bg-yellow-900/10' },
  INFO:     { dot: 'bg-blue-500',   border: 'border-blue-500',   bg: ''                 },
}

function timeAgo(isoString) {
  const secs = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000)
  if (secs < 60)    return `${secs}s ago`
  if (secs < 3600)  return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

export default function NotificationPanel({ isOpen, onClose }) {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchNotifications = async () => {
    setLoading(true)
    try {
      const res = await axios.get('/api/notifications')
      setNotifications(res.data)
    } catch (err) {
      console.error('Failed to fetch notifications:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) fetchNotifications()
  }, [isOpen])

  const handleMarkRead = async (id) => {
    try {
      await axios.post(`/api/notifications/${id}/read`)
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    } catch (err) {
      console.error('Failed to mark notification read:', err)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await axios.post('/api/notifications/read-all')
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch (err) {
      console.error('Failed to mark all read:', err)
    }
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length

  return (
    <div className={`fixed inset-0 z-50 ${isOpen ? '' : 'pointer-events-none'}`}>
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/50 transition-opacity duration-200 ${isOpen ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
      />

      {/* Slide-in panel */}
      <div
        className={`absolute right-0 top-0 h-full w-80 sm:w-96 bg-gray-900 border-l border-gray-700 shadow-2xl flex flex-col transition-transform duration-300 ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-700 flex-shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-white">Notifications</h2>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 font-medium leading-none">
                {unreadCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                Mark all read
              </button>
            )}
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-300 transition-colors"
              aria-label="Close notifications"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>

        {/* Notification list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-sm text-gray-500">
              Loading…
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-center px-4">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-gray-700 mb-3">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              <p className="text-sm text-gray-400">No notifications</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {notifications.map((n) => {
                const style = SEVERITY_STYLE[n.severity] || SEVERITY_STYLE.INFO
                return (
                  <button
                    key={n.id}
                    onClick={() => !n.is_read && handleMarkRead(n.id)}
                    className={`w-full text-left px-4 py-3 hover:bg-gray-800 transition-colors ${!n.is_read ? `${style.bg} border-l-2 ${style.border}` : ''}`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${style.dot} ${n.is_read ? 'opacity-30' : ''}`}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2 mb-0.5">
                          <span className={`text-xs font-medium truncate ${n.is_read ? 'text-gray-500' : 'text-gray-200'}`}>
                            {n.device}
                          </span>
                          <span className="text-xs text-gray-600 flex-shrink-0">
                            {timeAgo(n.timestamp)}
                          </span>
                        </div>
                        <p className={`text-xs leading-snug ${n.is_read ? 'text-gray-600' : 'text-gray-400'}`}>
                          {n.message}
                        </p>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
