import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { isAuthenticated, setTokens, clearTokens, getAccessToken } from './lib/auth'
import { api } from './lib/api'
import LoginPage from './pages/LoginPage'
import CallbackPage from './pages/CallbackPage'
import DashboardPage from './pages/DashboardPage'
import ChecksPage from './pages/ChecksPage'
import CheckDetailPage from './pages/CheckDetailPage'
import TeamSettingsPage from './pages/TeamSettingsPage'
import SharedAlertsPage from './pages/SharedAlertsPage'
import AlertChannelsPage from './pages/AlertChannelsPage'

function App() {
  const [authenticated, setAuthenticated] = useState(isAuthenticated())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    if (authenticated) {
      loadUser()
    } else {
      setLoading(false)
    }
  }, [authenticated])
  
  async function loadUser() {
    try {
      console.log('Loading user with token:', getAccessToken()?.substring(0, 20) + '...')
      const userData = await api.getMe()
      console.log('User loaded successfully:', userData)
      setUser(userData)
    } catch (error) {
      console.error('Failed to load user:', error)
      console.log('Clearing tokens and redirecting to login')
      clearTokens()
      setAuthenticated(false)
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
        <Route path="/login" element={<LoginPage />} />
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

export default App
