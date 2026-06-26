import React from 'react'
import AlertBanner from './components/AlertBanner'
import Dashboard from './components/Dashboard'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <AlertBanner />
      <Dashboard />
    </div>
  )
}
