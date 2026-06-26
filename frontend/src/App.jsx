import React, { useState } from 'react'
import AIInsights from './components/AIInsights'
import AlertBanner from './components/AlertBanner'
import Dashboard from './components/Dashboard'

const TABS = ['Dashboard', 'AI Insights']

export default function App() {
  const [activeTab, setActiveTab] = useState('Dashboard')

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <AlertBanner />

      <nav className="border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex gap-1">
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
      </nav>

      {activeTab === 'Dashboard' ? <Dashboard /> : <AIInsights />}
    </div>
  )
}
