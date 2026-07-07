import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Users, Grid3X3, List, CheckCircle, AlertCircle, Clock, PauseCircle } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function DashboardPage({ user, onLogout }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [teams, setTeams] = useState([])
  const [checksByTeam, setChecksByTeam] = useState(null) // null = not yet loaded
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreateTeam, setShowCreateTeam] = useState(false)
  const [newTeamName, setNewTeamName] = useState('')
  const [creating, setCreating] = useState(false)
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('dashboardViewMode') || 'grid')

  useEffect(() => {
    loadTeams()
    const interval = setInterval(loadTeams, 60000) // Refresh fleet status every 60s
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    localStorage.setItem('dashboardViewMode', viewMode)
  }, [viewMode])

  async function loadTeams() {
    try {
      const data = await api.listTeams()
      // Backend returns array directly, not wrapped in {teams: [...]}
      const loadedTeams = Array.isArray(data) ? data : data.teams || []
      setTeams(loadedTeams)
      setError(null)
      loadFleetStatus(loadedTeams)
    } catch {
      setError('Failed to load teams. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function loadFleetStatus(loadedTeams) {
    const results = await Promise.all(
      loadedTeams.map(async (team) => {
        try {
          const data = await api.listChecks(team.teamId)
          return [team.teamId, Array.isArray(data) ? data : data.checks || []]
        } catch {
          return [team.teamId, null] // null = failed to load, distinct from empty
        }
      })
    )
    setChecksByTeam(Object.fromEntries(results))
  }

  const fleet = (() => {
    if (!checksByTeam) return null
    const summary = { up: 0, late: 0, pending: 0, paused: 0, total: 0, lateChecks: [] }
    for (const team of teams) {
      const checks = checksByTeam[team.teamId]
      if (!checks) continue
      for (const check of checks) {
        summary.total++
        if (check.status === 'late') {
          summary.late++
          summary.lateChecks.push({ ...check, teamName: team.name })
        } else if (check.status === 'paused') {
          summary.paused++
        } else if (check.status === 'pending') {
          summary.pending++
        } else {
          summary.up++
        }
      }
    }
    return summary
  })()

  function teamStatusSummary(teamId) {
    const checks = checksByTeam?.[teamId]
    if (!checks) return null
    const late = checks.filter(c => c.status === 'late').length
    return { total: checks.length, late }
  }
  
  async function handleCreateTeam(e) {
    e.preventDefault()
    if (!newTeamName.trim()) return
    
    setCreating(true)
    try {
      const team = await api.createTeam(newTeamName.trim())
      setTeams([...teams, team])
      setNewTeamName('')
      setShowCreateTeam(false)
      toast.success('Team created successfully')
    } catch (error) {
      toast.error('Failed to create team: ' + error.message)
    } finally {
      setCreating(false)
    }
  }
  
  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="space-y-6">
        {/* Fleet status — answers "is anything down right now?" */}
        {fleet && fleet.total > 0 && (
          <div className="space-y-4">
            {fleet.lateChecks.length > 0 ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center mb-2">
                  <AlertCircle className="h-5 w-5 text-red-500 mr-2" aria-hidden="true" />
                  <h2 className="text-sm font-semibold text-red-800">
                    {fleet.lateChecks.length} {fleet.lateChecks.length === 1 ? 'check is' : 'checks are'} late
                  </h2>
                </div>
                <ul className="space-y-1">
                  {fleet.lateChecks.slice(0, 10).map((check) => (
                    <li key={check.checkId}>
                      <button
                        onClick={() => navigate(`/teams/${check.teamId}/checks/${check.checkId}`)}
                        className="text-sm text-red-700 hover:text-red-900 hover:underline"
                      >
                        {check.name} <span className="text-red-500">— {check.teamName}</span>
                      </button>
                    </li>
                  ))}
                  {fleet.lateChecks.length > 10 && (
                    <li className="text-sm text-red-500">…and {fleet.lateChecks.length - 10} more</li>
                  )}
                </ul>
              </div>
            ) : (
              <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center">
                <CheckCircle className="h-5 w-5 text-green-500 mr-2" aria-hidden="true" />
                <p className="text-sm font-medium text-green-800">
                  All systems operational — {fleet.up} {fleet.up === 1 ? 'check' : 'checks'} up
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { label: 'Up', count: fleet.up, Icon: CheckCircle, iconColor: 'text-green-500' },
                { label: 'Late', count: fleet.late, Icon: AlertCircle, iconColor: 'text-red-500' },
                { label: 'Pending', count: fleet.pending, Icon: Clock, iconColor: 'text-amber-500' },
                { label: 'Paused', count: fleet.paused, Icon: PauseCircle, iconColor: 'text-gray-400' },
              ].map(({ label, count, Icon, iconColor }) => (
                <div key={label} className="bg-white shadow rounded-lg px-4 py-3 flex items-center">
                  <Icon className={`h-6 w-6 ${iconColor} mr-3 flex-shrink-0`} aria-hidden="true" />
                  <div>
                    <p className="text-2xl font-semibold text-gray-900">{count}</p>
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Your Teams</h1>
          <div className="flex items-center space-x-3">
            <div className="flex rounded-md shadow-sm">
              <button
                onClick={() => setViewMode('grid')}
                className={`px-3 py-2 text-sm font-medium rounded-l-md border ${
                  viewMode === 'grid'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                <Grid3X3 className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`px-3 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
                  viewMode === 'table'
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                <List className="h-4 w-4" />
              </button>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => navigate('/shared-alerts')}
                className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-5 5-5-5h5v-12h5v12z" />
                </svg>
                Shared Alerts
              </button>
              <button
                onClick={() => setShowCreateTeam(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <Plus className="h-4 w-4 mr-2" />
                New Team
              </button>
            </div>
          </div>
        </div>
        
        {showCreateTeam && (
          <div className="bg-white shadow sm:rounded-lg p-6">
            <form onSubmit={handleCreateTeam} className="space-y-4">
              <div>
                <label htmlFor="teamName" className="block text-sm font-medium text-gray-700">
                  Team Name
                </label>
                <input
                  type="text"
                  id="teamName"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="My Team"
                  autoFocus
                />
              </div>
              <div className="flex space-x-3">
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Team'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateTeam(false)}
                  className="inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
        
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="ml-auto -mx-1.5 -my-1.5 rounded-lg focus:ring-2 focus:ring-red-500 p-1.5 inline-flex h-8 w-8 text-red-500 hover:bg-red-100"
              >
                <span className="sr-only">Dismiss</span>
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        ) : teams.length === 0 ? (
          <div className="text-center py-12 bg-white shadow sm:rounded-lg">
            <Users className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No teams</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating a new team.</p>
          </div>
        ) : (
          viewMode === 'grid' ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {teams.map((team) => (
                <div
                  key={team.teamId}
                  onClick={() => navigate(`/teams/${team.teamId}/checks`)}
                  className="bg-white overflow-hidden shadow rounded-lg hover:shadow-md transition-shadow cursor-pointer"
                >
                  <div className="p-5">
                    <div className="flex items-center">
                      <div className="flex-shrink-0">
                        <Users className="h-6 w-6 text-gray-400" />
                      </div>
                      <div className="ml-5 w-0 flex-1">
                        <dl>
                          <dt className="text-sm font-medium text-gray-500 truncate">Team</dt>
                          <dd className="text-lg font-medium text-gray-900">{team.name}</dd>
                        </dl>
                      </div>
                    </div>
                    {(() => {
                      const status = teamStatusSummary(team.teamId)
                      if (!status) return null
                      return (
                        <p className="mt-2 text-sm">
                          <span className="text-gray-500">{status.total} {status.total === 1 ? 'check' : 'checks'}</span>
                          {status.late > 0 && (
                            <span className="ml-2 inline-flex items-center font-medium text-red-700">
                              <AlertCircle className="h-4 w-4 mr-1" aria-hidden="true" />
                              {status.late} late
                            </span>
                          )}
                        </p>
                      )
                    })()}
                    <div className="mt-4 flex items-center justify-between">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {team.role}
                      </span>
                      {team.role === 'admin' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/teams/${team.teamId}/settings`);
                          }}
                          className="text-sm text-gray-600 hover:text-gray-500"
                        >
                          Settings
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <ul className="divide-y divide-gray-200">
                {teams.map((team) => (
                  <li
                    key={team.teamId}
                    onClick={() => navigate(`/teams/${team.teamId}/checks`)}
                    className="hover:bg-gray-50 cursor-pointer"
                  >
                    <div className="px-4 py-4 sm:px-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <Users className="h-5 w-5 text-gray-400" />
                          <p className="text-sm font-medium text-blue-600 truncate">{team.name}</p>
                          {(() => {
                            const status = teamStatusSummary(team.teamId)
                            if (!status) return null
                            return (
                              <span className="text-sm text-gray-500">
                                {status.total} {status.total === 1 ? 'check' : 'checks'}
                                {status.late > 0 && (
                                  <span className="ml-2 inline-flex items-center font-medium text-red-700">
                                    <AlertCircle className="h-4 w-4 mr-1" aria-hidden="true" />
                                    {status.late} late
                                  </span>
                                )}
                              </span>
                            )
                          })()}
                        </div>
                        <div className="flex items-center space-x-3">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {team.role}
                          </span>
                          {team.role === 'admin' && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/teams/${team.teamId}/settings`);
                              }}
                              className="text-sm text-gray-600 hover:text-gray-500"
                            >
                              Settings
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )
        )}
      </div>
    </Layout>
  )
}
