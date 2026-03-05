import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Plus, CheckCircle, AlertCircle, PauseCircle, ArrowLeft, Bell, MoreVertical, RotateCcw, Trash2, Settings, Play } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Layout from '../components/Layout'
import { api } from '../lib/api'

export default function ChecksPage({ user, onLogout }) {
  const { teamId } = useParams()
  const navigate = useNavigate()
  const [checks, setChecks] = useState([])
  const [team, setTeam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showCreateCheck, setShowCreateCheck] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    periodSeconds: 60, // 1 minute in seconds
    graceSeconds: 300, // 5 minutes in seconds
    alertChannels: [], // Selected alert channel IDs
  })
  const [creating, setCreating] = useState(false)
  const [availableChannels, setAvailableChannels] = useState([])
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null)
  const [showRotateConfirm, setShowRotateConfirm] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [selectedChecks, setSelectedChecks] = useState(new Set())
  const [bulkActionLoading, setBulkActionLoading] = useState(false)
  const [showQuickEdit, setShowQuickEdit] = useState(null)
  const [quickEditData, setQuickEditData] = useState({
    name: '',
    periodSeconds: 60, // 1 minute in seconds
    graceSeconds: 300, // 5 minutes in seconds
  })
  const [quickEditLoading, setQuickEditLoading] = useState(false)
  
  useEffect(() => {
    loadTeam()
    loadChecks()
    loadAlertChannels()
    const interval = setInterval(loadChecks, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [teamId])
  
  async function loadTeam() {
    try {
      const teamData = await api.getTeam(teamId)
      setTeam(teamData)
    } catch (error) {
      console.error('Failed to load team:', error)
    }
  }
  
  async function loadChecks() {
    try {
      const data = await api.listChecks(teamId)
      // Backend returns array directly, not wrapped in {checks: [...]}
      setChecks(Array.isArray(data) ? data : data.checks || [])
    } catch (error) {
      console.error('Failed to load checks:', error)
    } finally {
      setLoading(false)
    }
  }
  
  async function loadAlertChannels() {
    try {
      // Load team-specific channels
      const teamChannels = await api.listAlertChannels(teamId)
      
      // Load shared channels from all teams
      const teamsData = await api.listTeams()
      const teams = Array.isArray(teamsData) ? teamsData : teamsData.teams || []
      
      const sharedChannels = []
      const seenChannels = new Set()
      
      for (const team of teams) {
        try {
          const channels = await api.listAlertChannels(team.teamId)
          const teamSharedChannels = channels.filter(channel => channel.shared)
          
          for (const channel of teamSharedChannels) {
            const channelKey = `${channel.teamId}-${channel.channelId}`
            if (!seenChannels.has(channelKey)) {
              seenChannels.add(channelKey)
              sharedChannels.push({
                ...channel,
                teamName: team.name,
                isShared: true
              })
            }
          }
        } catch (error) {
          console.error(`Failed to load channels for team ${team.teamId}:`, error)
        }
      }
      
      // Combine team channels and shared channels
      const allChannels = [
        ...(Array.isArray(teamChannels) ? teamChannels : []),
        ...sharedChannels
      ]
      
      setAvailableChannels(allChannels)
    } catch (error) {
      console.error('Failed to load alert channels:', error)
    }
  }

  async function handleCreateCheck(e) {
    e.preventDefault()
    setCreating(true)
    try {
      await api.createCheck(teamId, formData)
      setFormData({ name: '', periodSeconds: 60, graceSeconds: 300, alertChannels: [] })
      setShowCreateCheck(false)
      loadChecks()
    } catch (error) {
      alert('Failed to create check: ' + error.message)
    } finally {
      setCreating(false)
    }
  }

  async function handleDeleteCheck(checkId) {
    setActionLoading(checkId)
    try {
      await api.deleteCheck(teamId, checkId)
      setShowDeleteConfirm(null)
      loadChecks()
    } catch (error) {
      alert('Failed to delete check: ' + error.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleRotateToken(checkId) {
    setActionLoading(checkId)
    try {
      await api.rotateCheckToken(teamId, checkId)
      setShowRotateConfirm(null)
      loadChecks()
      alert('Token rotated successfully. Please update your monitoring scripts with the new token.')
    } catch (error) {
      alert('Failed to rotate token: ' + error.message)
    } finally {
      setActionLoading(null)
    }
  }

  function toggleCheckSelection(checkId) {
    const newSelected = new Set(selectedChecks)
    if (newSelected.has(checkId)) {
      newSelected.delete(checkId)
    } else {
      newSelected.add(checkId)
    }
    setSelectedChecks(newSelected)
  }

  function toggleSelectAll() {
    if (selectedChecks.size === checks.length) {
      setSelectedChecks(new Set())
    } else {
      setSelectedChecks(new Set(checks.map(c => c.checkId)))
    }
  }

  async function handleBulkPause() {
    if (selectedChecks.size === 0) return
    
    setBulkActionLoading(true)
    try {
      const response = await api.bulkPauseChecks(teamId, Array.from(selectedChecks))
      alert(response.message)
      setSelectedChecks(new Set())
      loadChecks()
    } catch (error) {
      alert('Failed to pause checks: ' + error.message)
    } finally {
      setBulkActionLoading(false)
    }
  }

  async function handleToggleCheckStatus(checkId, currentStatus) {
    setActionLoading(checkId)
    try {
      if (currentStatus === 'paused') {
        await api.resumeCheck(teamId, checkId)
      } else {
        await api.pauseCheck(teamId, checkId)
      }
      loadChecks()
    } catch (error) {
      alert(`Failed to ${currentStatus === 'paused' ? 'resume' : 'pause'} check: ` + error.message)
    } finally {
      setActionLoading(null)
    }
  }

  function openQuickEdit(check) {
    setQuickEditData({
      name: check.name,
      periodSeconds: check.periodSeconds,
      graceSeconds: check.graceSeconds,
    })
    setShowQuickEdit(check.checkId)
  }

  async function handleQuickEdit(e) {
    e.preventDefault()
    setQuickEditLoading(true)
    try {
      await api.updateCheck(teamId, showQuickEdit, quickEditData)
      setShowQuickEdit(null)
      loadChecks()
    } catch (error) {
      alert('Failed to update check: ' + error.message)
    } finally {
      setQuickEditLoading(false)
    }
  }
  
  function getStatusIcon(status) {
    switch (status) {
      case 'up':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'late':
        return <AlertCircle className="h-5 w-5 text-red-500" />
      case 'paused':
        return <PauseCircle className="h-5 w-5 text-gray-400" />
      default:
        return null
    }
  }
  
  function getStatusBadge(status) {
    const classes = {
      up: 'bg-green-100 text-green-800',
      late: 'bg-red-100 text-red-800',
      paused: 'bg-gray-100 text-gray-800',
    }
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${classes[status]}`}>
        {status.toUpperCase()}
      </span>
    )
  }
  
  function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
    return `${Math.floor(seconds / 86400)}d`
  }
  
  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Teams
            </button>
            <div>
              {team ? (
                <h1 className="text-3xl font-bold text-gray-900">
                  Team{' '}
                  <button
                    onClick={() => navigate(`/teams/${teamId}/settings`)}
                    className="text-blue-600 hover:text-blue-800 underline"
                  >
                    {team.name}
                  </button>{' '}
                  Checks
                </h1>
              ) : (
                <h1 className="text-3xl font-bold text-gray-900">Checks</h1>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate(`/teams/${teamId}/settings`)}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <Settings className="h-4 w-4 mr-2" />
              Team Settings
            </button>
            <button
              onClick={() => setShowCreateCheck(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Check
            </button>
          </div>
        </div>
        
        {showCreateCheck && (
          <div className="bg-white shadow sm:rounded-lg p-6">
            <form onSubmit={handleCreateCheck} className="space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                  Check Name
                </label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  placeholder="Daily Backup Job"
                  required
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="period" className="block text-sm font-medium text-gray-700">
                    Period (minutes)
                  </label>
                  <input
                    type="number"
                    id="period"
                    value={Math.round(formData.periodSeconds / 60)}
                    onChange={(e) => setFormData({ ...formData, periodSeconds: parseInt(e.target.value) * 60 })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    min="1"
                    required
                  />
                  <p className="mt-1 text-xs text-gray-500">How often the job runs</p>
                </div>
                
                <div>
                  <label htmlFor="grace" className="block text-sm font-medium text-gray-700">
                    Grace (minutes)
                  </label>
                  <input
                    type="number"
                    id="grace"
                    value={Math.round(formData.graceSeconds / 60)}
                    onChange={(e) => setFormData({ ...formData, graceSeconds: parseInt(e.target.value) * 60 })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    min="0"
                    required
                  />
                  <p className="mt-1 text-xs text-gray-500">Extra time before alert</p>
                </div>
              </div>
              
              {/* Alert Channels Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Alert Channels
                </label>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {availableChannels.map((channel) => (
                    <label key={channel.channelId} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={formData.alertChannels.includes(channel.channelId)}
                        onChange={(e) => {
                          const channelId = channel.channelId
                          const currentChannels = formData.alertChannels || []
                          if (e.target.checked) {
                            setFormData({ ...formData, alertChannels: [...currentChannels, channelId] })
                          } else {
                            setFormData({ ...formData, alertChannels: currentChannels.filter(id => id !== channelId) })
                          }
                        }}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <span className="ml-2 text-sm text-gray-700">
                        {channel.displayName || channel.name} ({channel.type})
                        {channel.isShared && (
                          <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                            <Users className="h-3 w-3 mr-1" />
                            Shared from {channel.teamName}
                          </span>
                        )}
                      </span>
                    </label>
                  ))}
                </div>
                {availableChannels.length === 0 && (
                  <p className="text-sm text-gray-500">No alert channels available. Create one in the Channels page.</p>
                )}
              </div>
              
              <div className="flex space-x-3">
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                  {creating ? 'Creating...' : 'Create Check'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateCheck(false)}
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
        ) : checks.length === 0 ? (
          <div className="text-center py-12 bg-white shadow sm:rounded-lg">
            <CheckCircle className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No checks</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating a new check.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Bulk Actions Bar */}
            {checks.length > 0 && (
              <div className="bg-white shadow sm:rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={selectedChecks.size === checks.length && checks.length > 0}
                        onChange={toggleSelectAll}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <span className="ml-2 text-sm text-gray-700">
                        Select all ({selectedChecks.size} of {checks.length} selected)
                      </span>
                    </label>
                  </div>
                  
                  {selectedChecks.size > 0 && (
                    <div className="flex space-x-2">
                      <button
                        onClick={handleBulkPause}
                        disabled={bulkActionLoading}
                        className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        <PauseCircle className="h-4 w-4 mr-1" />
                        Pause ({selectedChecks.size})
                      </button>
                      <button
                        onClick={handleBulkResume}
                        disabled={bulkActionLoading}
                        className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Resume ({selectedChecks.size})
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <ul className="divide-y divide-gray-200">
                {checks.map((check) => (
                <li
                  key={check.checkId}
                  className="hover:bg-gray-50"
                >
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <input
                          type="checkbox"
                          checked={selectedChecks.has(check.checkId)}
                          onChange={() => toggleCheckSelection(check.checkId)}
                          onClick={(e) => e.stopPropagation()}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <div 
                          onClick={() => navigate(`/teams/${teamId}/checks/${check.checkId}`)}
                          className="flex items-center space-x-3 cursor-pointer flex-1"
                        >
                          {getStatusIcon(check.status)}
                          <p className="text-sm font-medium text-blue-600 truncate">{check.name}</p>
                          {check.alertTopics && check.alertTopics.length > 0 && (
                            <div className="flex items-center">
                              <Bell className="h-4 w-4 text-orange-500" title={`${check.alertTopics.length} alert topic(s) configured`} />
                              <span className="text-xs text-orange-600 ml-1">{check.alertTopics.length}</span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {getStatusBadge(check.status)}
                        <div className="flex space-x-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleToggleCheckStatus(check.checkId, check.status)
                            }}
                            className={`p-1 rounded ${
                              check.status === 'paused' 
                                ? 'text-gray-400 hover:text-green-600 hover:bg-green-50' 
                                : 'text-gray-400 hover:text-yellow-600 hover:bg-yellow-50'
                            }`}
                            title={check.status === 'paused' ? 'Resume Check' : 'Pause Check'}
                            disabled={actionLoading === check.checkId}
                          >
                            {check.status === 'paused' ? (
                              <CheckCircle className="h-4 w-4" />
                            ) : (
                              <PauseCircle className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              openQuickEdit(check)
                            }}
                            className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="Quick Edit"
                            disabled={actionLoading === check.checkId}
                          >
                            <Settings className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setShowRotateConfirm(check.checkId)
                            }}
                            className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="Rotate Token"
                            disabled={actionLoading === check.checkId}
                          >
                            <RotateCcw className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setShowDeleteConfirm(check.checkId)
                            }}
                            className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                            title="Delete Check"
                            disabled={actionLoading === check.checkId}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="mt-2 sm:flex sm:justify-between">
                      <div className="sm:flex space-x-4">
                        <p className="flex items-center text-sm text-gray-500">
                          Period: {formatDuration(check.periodSeconds)}
                        </p>
                        <p className="flex items-center text-sm text-gray-500">
                          Grace: {formatDuration(check.graceSeconds)}
                        </p>
                      </div>
                      <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                        {check.lastPingAt ? (
                          <p>Last ping {formatDistanceToNow(new Date(check.lastPingAt), { addSuffix: true })}</p>
                        ) : (
                          <p>No pings yet</p>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mt-4">Delete Check</h3>
              <div className="mt-2 px-7 py-3">
                <p className="text-sm text-gray-500">
                  Are you sure you want to delete this check? This action cannot be undone and will delete all ping history.
                </p>
              </div>
              <div className="items-center px-4 py-3">
                <button
                  onClick={() => handleDeleteCheck(showDeleteConfirm)}
                  disabled={actionLoading === showDeleteConfirm}
                  className="px-4 py-2 bg-red-600 text-white text-base font-medium rounded-md w-full shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:opacity-50"
                >
                  {actionLoading === showDeleteConfirm ? 'Deleting...' : 'Delete'}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(null)}
                  disabled={actionLoading === showDeleteConfirm}
                  className="mt-3 px-4 py-2 bg-white text-gray-500 text-base font-medium rounded-md w-full shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Rotate Token Confirmation Modal */}
      {showRotateConfirm && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100">
                <RotateCcw className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mt-4">Rotate Token</h3>
              <div className="mt-2 px-7 py-3">
                <p className="text-sm text-gray-500">
                  This will generate a new token for this check. You'll need to update your monitoring scripts with the new token. The old token will stop working immediately.
                </p>
              </div>
              <div className="items-center px-4 py-3">
                <button
                  onClick={() => handleRotateToken(showRotateConfirm)}
                  disabled={actionLoading === showRotateConfirm}
                  className="px-4 py-2 bg-blue-600 text-white text-base font-medium rounded-md w-full shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
                >
                  {actionLoading === showRotateConfirm ? 'Rotating...' : 'Rotate Token'}
                </button>
                <button
                  onClick={() => setShowRotateConfirm(null)}
                  disabled={actionLoading === showRotateConfirm}
                  className="mt-3 px-4 py-2 bg-white text-gray-500 text-base font-medium rounded-md w-full shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Edit Modal */}
      {showQuickEdit && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100">
                <Settings className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mt-4 text-center">Quick Edit Check</h3>
              <form onSubmit={handleQuickEdit} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="quickEditName" className="block text-sm font-medium text-gray-700">
                    Check Name
                  </label>
                  <input
                    type="text"
                    id="quickEditName"
                    value={quickEditData.name}
                    onChange={(e) => setQuickEditData({ ...quickEditData, name: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    required
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="quickEditPeriod" className="block text-sm font-medium text-gray-700">
                      Period (minutes)
                    </label>
                    <input
                      type="number"
                      id="quickEditPeriod"
                      value={Math.round(quickEditData.periodSeconds / 60)}
                      onChange={(e) => setQuickEditData({ ...quickEditData, periodSeconds: parseInt(e.target.value) * 60 })}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      min="1"
                      required
                    />
                  </div>
                  
                  <div>
                    <label htmlFor="quickEditGrace" className="block text-sm font-medium text-gray-700">
                      Grace (minutes)
                    </label>
                    <input
                      type="number"
                      id="quickEditGrace"
                      value={Math.round(quickEditData.graceSeconds / 60)}
                      onChange={(e) => setQuickEditData({ ...quickEditData, graceSeconds: parseInt(e.target.value) * 60 })}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      min="0"
                      required
                    />
                  </div>
                </div>
                
                <div className="flex space-x-3 pt-4">
                  <button
                    type="submit"
                    disabled={quickEditLoading}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white text-base font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
                  >
                    {quickEditLoading ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowQuickEdit(null)}
                    disabled={quickEditLoading}
                    className="flex-1 px-4 py-2 bg-white text-gray-500 text-base font-medium rounded-md shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
