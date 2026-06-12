import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { isAuthenticated, setTokens, clearTokens } from './lib/auth'
import { api } from './lib/api'
import LoginPage from './pages/LoginPage'
import CallbackPage from './pages/CallbackPage'
import DashboardPage from './pages/DashboardPage'
import ChecksPage from './pages/ChecksPage'
import CheckDetailPage from './pages/CheckDetailPage'
import TeamSettingsPage from './pages/TeamSettingsPage'
import SharedAlertsPage from './pages/SharedAlertsPage'
import AlertChannelsPage from './pages/AlertChannelsPage'
import { ToastProvider, useToast } from './components/Toast'

function AppShell() {
  const toast = useToast()
  const [authenticated, setAuthenticated] = useState(isAuthenticated())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const handleAuthExpired = (event) => {
      const message = event?.detail?.message || 'Your session expired. Please sign in again.'
      clearTokens()
      setUser(null)
      setAuthenticated(false)
      setLoading(false)
      toast.error(message)
    }

    window.addEventListener('pulsechecks:auth-expired', handleAuthExpired)
    return () => window.removeEventListener('pulsechecks:auth-expired', handleAuthExpired)
  }, [toast])
  
  useEffect(() => {
    if (authenticated) {
      loadUser()
    } else {
      setLoading(false)
    }
  }, [authenticated])
  
  async function loadUser() {
    try {
      const userData = await api.getMe()
      setUser(userData)
    } catch {
      clearTokens()
      setAuthenticated(false)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }
  
  function handleLogin(tokens) {
    setTokens(tokens)
    setAuthenticated(true)
  }
  
  function handleLogout() {
    clearTokens()
    setAuthenticated(false)
    setUser(null)
  }
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }
  
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
        <Route path="/callback" element={<CallbackPage onLogin={handleLogin} />} />
        
        {authenticated ? (
          <>
            <Route path="/" element={<DashboardPage user={user} onLogout={handleLogout} />} />
            <Route path="/shared-alerts" element={<SharedAlertsPage user={user} onLogout={handleLogout} />} />
            <Route path="/teams/:teamId/checks" element={<ChecksPage user={user} onLogout={handleLogout} />} />
            <Route path="/teams/:teamId/checks/:checkId" element={<CheckDetailPage user={user} onLogout={handleLogout} />} />
            <Route path="/teams/:teamId/settings" element={<TeamSettingsPage user={user} onLogout={handleLogout} />} />
            <Route path="/teams/:teamId/channels" element={<AlertChannelsPage user={user} onLogout={handleLogout} />} />
          </>
        ) : (
          <Route path="*" element={<Navigate to="/login" replace />} />
        )}
      </Routes>
    </BrowserRouter>
  )
}

function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  )
}

export default App
