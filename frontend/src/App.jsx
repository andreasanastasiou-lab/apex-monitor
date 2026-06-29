import React, { useState } from 'react'
import AIInsights from './components/AIInsights'
import AlertBanner from './components/AlertBanner'
import Dashboard from './components/Dashboard'
import DeviceInventory from './components/DeviceInventory'
import Login from './components/Login'
import { AuthProvider, useAuth } from './context/AuthContext'

function AuthenticatedApp() {
  const { user, logout } = useAuth()
  const isAdmin = user?.role === 'admin'
  const TABS = ['Dashboard', 'AI Insights', ...(isAdmin ? ['Devices'] : [])]
  const [activeTab, setActiveTab] = useState('Dashboard')

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <AlertBanner />

      <nav className="border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between">
          <div className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* User info + logout */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">
              {user?.username}
              {user?.role === 'admin' && (
                <span className="ml-1.5 text-blue-500 font-medium">admin</span>
              )}
            </span>
            <button
              onClick={logout}
              className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 px-2.5 py-1 rounded transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </nav>

      {activeTab === 'Dashboard' && <Dashboard />}
      {activeTab === 'AI Insights' && <AIInsights />}
      {activeTab === 'Devices' && <DeviceInventory />}
    </div>
  )
}

export default function App() {
  const { isAuthenticated } = useAuth()

  return isAuthenticated ? <AuthenticatedApp /> : <Login />
}

// Wrap at the module boundary so useAuth() works everywhere in the tree.
export function AppWithAuth() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  )
}
