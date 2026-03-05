import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Copy, Pause, Play, Clock, Activity as ActivityIcon, Bell, Users } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { config } from '../config'

// Helper function to get the proper ping base URL (custom domain if available)
function getPingBaseUrl() {
  // If using AWS API Gateway raw domain, convert to custom domain
  if (config.apiUrl.includes('amazonaws.com')) {
    // Extract domain from current page URL and construct custom API domain
    const currentDomain = window.location.hostname
    return `https://api.${currentDomain}`
  }
  return config.apiUrl
}

export default function CheckDetailPage({ user, onLogout }) {
  const { teamId, checkId } = useParams()
  const navigate = useNavigate()
  const [check, setCheck] = useState(null)
  const [pings, setPings] = useState([])
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const [selectedPing, setSelectedPing] = useState(null)
  const [availableTopics, setAvailableTopics] = useState([])
  const [availableChannels, setAvailableChannels] = useState([])
  const [showAlertSettings, setShowAlertSettings] = useState(false)

  useEffect(() => {
    loadCheckData()
    loadAlertTopics()
    loadAlertChannels()
    const interval = setInterval(() => {
      loadCheckData()
      loadAlertChannels() // Refresh channels too
    }, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [teamId, checkId])

  async function loadCheckData() {
    try {
      const [checkData, pingsData] = await Promise.all([
        api.getCheck(teamId, checkId),
        api.listPings(teamId, checkId, 20),
      ])
      // Construct pingUrl from token if not provided by backend
      if (checkData.token && !checkData.pingUrl) {
        checkData.pingUrl = `${getPingBaseUrl()}/ping/${checkData.token}`
      }
      setCheck(checkData)
      // Backend returns array directly, not wrapped in {pings: [...]}
      setPings(Array.isArray(pingsData) ? pingsData : pingsData.pings || [])
    } catch (error) {
      console.error('Failed to load check:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadAlertTopics() {
    try {
      const channels = await api.listAlertChannels(teamId)
      setAvailableTopics(Array.isArray(channels) ? channels : [])
    } catch (error) {
      console.error('Failed to load alert topics:', error)
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

  async function updateCheckAlertChannels(selectedChannelIds) {
    // Optimistic update
    setCheck(prev => ({ ...prev, alertChannels: selectedChannelIds }))

    try {
      const updatedCheck = await api.updateCheck(teamId, checkId, { alertChannels: selectedChannelIds })
      // Update with server response to ensure consistency
      setCheck(updatedCheck)
    } catch (error) {
      alert('Failed to update alert channels: ' + error.message)
      // Revert on error
      loadCheckData()
    }
  }

  async function updateCheckAlertTopics(selectedTopicArns) {
    // Optimistic update
    setCheck(prev => ({ ...prev, alertChannels: selectedTopicArns }))

    try {
      const updatedCheck = await api.updateCheck(teamId, checkId, { alertChannels: selectedTopicArns })
      // Update with server response to ensure consistency
      setCheck(updatedCheck)
    } catch (error) {
      alert('Failed to update alert topics: ' + error.message)
      // Revert on error
      loadCheckData()
    }
  }

  async function handlePause() {
    try {
      await api.pauseCheck(teamId, checkId)
      loadCheckData()
    } catch (error) {
      alert('Failed to pause check: ' + error.message)
    }
  }

  async function handleResume() {
    try {
      await api.resumeCheck(teamId, checkId)
      loadCheckData()
    } catch (error) {
      alert('Failed to resume check: ' + error.message)
    }
  }

  async function handleRotateToken() {
    if (!confirm('Are you sure you want to rotate the token? The old ping URL will stop working immediately.')) {
      return
    }

    try {
      const updatedCheck = await api.rotateCheckToken(teamId, checkId)
      // Update check with new token and ping URL
      updatedCheck.pingUrl = `${getPingBaseUrl()}/ping/${updatedCheck.token}`
      setCheck(updatedCheck)
      alert('Token rotated successfully! Please update your monitoring scripts with the new ping URL.')
    } catch (error) {
      alert('Failed to rotate token: ' + error.message)
    }
  }

  async function handleDeleteCheck() {
    if (!confirm(`Are you sure you want to delete "${check.name}"? This action cannot be undone and will delete all ping history.`)) {
      return
    }

    try {
      await api.deleteCheck(teamId, checkId)
      alert('Check deleted successfully')
      navigate(`/teams/${teamId}/checks`)
    } catch (error) {
      alert('Failed to delete check: ' + error.message)
    }
  }

  function copyPingUrl() {
    if (check?.pingUrl) {
      navigator.clipboard.writeText(check.pingUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
    return `${Math.floor(seconds / 86400)}d`
  }

  if (loading) {
    return (
      <Layout user={user} onLogout={onLogout}>
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        </div>
      </Layout>
    )
  }

  if (!check) {
    return (
      <Layout user={user} onLogout={onLogout}>
        <div className="text-center py-12">
          <p className="text-gray-500">Check not found</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate(`/teams/${teamId}/checks`)}
              className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Checks
            </button>
          </div>
          <div className="flex space-x-3">
            {check.status === 'paused' ? (
              <button
                onClick={handleResume}
                className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <Play className="h-4 w-4 mr-2" />
                Resume
              </button>
            ) : (
              <button
                onClick={handlePause}
                className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                <Pause className="h-4 w-4 mr-2" />
                Pause
              </button>
            )}
            <button
              onClick={handleDeleteCheck}
              className="inline-flex items-center px-4 py-2 border border-red-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            >
              🗑️ Delete
            </button>
          </div>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">{check.name}</h3>
            <p className="mt-1 max-w-2xl text-sm text-gray-500">
              Status: <span className={`font-medium ${
                check.status === 'up' ? 'text-green-600' :
                check.status === 'late' ? 'text-red-600' :
                'text-gray-600'
              }`}>{check.status.toUpperCase()}</span>
            </p>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Ping URL</dt>
                <dd className="mt-1 flex items-center space-x-2">
                  <code className="flex-1 text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded border border-gray-200 overflow-x-auto">
                    {check.pingUrl}
                  </code>
                  <button
                    onClick={copyPingUrl}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    title="Copy URL"
                  >
                    <Copy className="h-4 w-4" />
                  </button>
                  <button
                    onClick={handleRotateToken}
                    className="inline-flex items-center px-3 py-2 border border-red-300 shadow-sm text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    title="Rotate Token (invalidates current URL)"
                  >
                    🔄
                  </button>
                </dd>
                {copied && <p className="mt-1 text-xs text-green-600">Copied!</p>}
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500 flex items-center">
                  <Clock className="h-4 w-4 mr-1" />
                  Period
                </dt>
                <dd className="mt-1 text-sm text-gray-900">{formatDuration(check.periodSeconds)}</dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500 flex items-center">
                  <Clock className="h-4 w-4 mr-1" />
                  Grace Period
                </dt>
                <dd className="mt-1 text-sm text-gray-900">{formatDuration(check.graceSeconds)}</dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500">Last Ping</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {check.lastPingAt ? formatDistanceToNow(new Date(check.lastPingAt), { addSuffix: true }) : 'Never'}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500">Created</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDistanceToNow(new Date(check.createdAt), { addSuffix: true })}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Unified Alert Configuration */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
                <Bell className="h-5 w-5 mr-2" />
                Alert Configuration
              </h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Configure notifications, escalation, and suppression for this check
              </p>
            </div>
            <button
              onClick={() => setShowAlertSettings(!showAlertSettings)}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              {showAlertSettings ? 'Hide' : 'Configure'}
            </button>
          </div>

          {showAlertSettings && (
            <div className="border-t border-gray-200 px-4 py-4">
              <div className="space-y-6">

                {/* Alert Channels */}
                <div>
                  <div className="text-sm font-medium text-gray-700 mb-3">
                    Alert Channels
                  </div>
                  <p className="text-sm text-gray-500 mb-3">
                    Select channels to notify when this check fails
                  </p>
                  {availableChannels.length === 0 ? (
                    <div className="text-sm text-gray-500">
                      No alert channels available.
                      <button
                        onClick={() => navigate(`/teams/${teamId}/channels`)}
                        className="text-blue-600 hover:text-blue-500 ml-1"
                      >
                        Create alert channels
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {availableChannels.map((channel) => {
                        const isSelected = check?.alertChannels?.includes(channel.channelId) || false

                        return (
                          <label key={channel.channelId} className="flex items-center">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                const currentChannels = check?.alertChannels || []
                                const newChannels = e.target.checked
                                  ? [...currentChannels, channel.channelId]
                                  : currentChannels.filter(id => id !== channel.channelId)
                                updateCheckAlertChannels(newChannels)
                              }}
                              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                            />
                            <span className="ml-2 text-sm text-gray-900">
                              {channel.displayName} ({channel.type.toUpperCase()})
                              {channel.isShared && (
                                <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                  <Users className="h-3 w-3 mr-1" />
                                  Shared from {channel.teamName}
                                </span>
                              )}
                            </span>
                          </label>
                        )
                      })}
                    </div>
                  )}

                  {check?.alertChannels && check.alertChannels.length > 0 && (
                    <div className="mt-3 p-3 bg-green-50 rounded-md">
                      <div className="text-sm text-green-800">
                        <strong>Active channels:</strong> {check.alertChannels.length} channel(s) will be notified when this check fails
                      </div>
                    </div>
                  )}
                </div>

                {/* You may want to add more alert configuration sections here, e.g., Alert Topics, etc. */}

              </div>
            </div>
          )}
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
              <ActivityIcon className="h-5 w-5 mr-2" />
              Recent Pings (Latest 20)
            </h3>
          </div>
          <div className="border-t border-gray-200">
            {pings.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No pings recorded yet
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {pings.map((ping) => (
                  <li
                    key={ping.timestamp}
                    className="px-4 py-3 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedPing(ping)}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <p className="text-sm text-gray-900">
                          {formatDistanceToNow(new Date(ping.receivedAt), { addSuffix: true })}
                        </p>
                        {ping.data && (
                          <p className="mt-1 text-xs text-gray-500 font-mono">{ping.data}</p>
                        )}
                      </div>
                      <span className="text-xs text-gray-400">
                        {new Date(ping.receivedAt).toLocaleString()}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <h4 className="text-sm font-medium text-blue-900 mb-2">Usage Example</h4>
          <pre className="text-xs text-blue-800 bg-white p-3 rounded border border-blue-200 overflow-x-auto">
            {`# Simple ping
curl ${check.pingUrl}

# With data
curl -X POST ${check.pingUrl} \\
  -H "Content-Type: application/json" \\
  -d "{\\"data\\": \\"Backup completed: 1.2GB\\"}"`}
          </pre>
        </div>
      </div>

      {/* Ping Detail Modal */}
      {selectedPing && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-3/4 lg:w-1/2 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Ping Details</h3>
                <button
                  onClick={() => setSelectedPing(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Received At</label>
                  <p className="mt-1 text-sm text-gray-900">
                    {new Date(selectedPing.receivedAt).toLocaleString()}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(selectedPing.receivedAt), { addSuffix: true })}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Timestamp</label>
                  <p className="mt-1 text-sm font-mono text-gray-900">{selectedPing.timestamp}</p>
                </div>

                {selectedPing.data && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Data</label>
                    <div className="mt-1 p-3 bg-gray-50 rounded-md border">
                      <pre className="text-sm text-gray-900 whitespace-pre-wrap font-mono">
                        {selectedPing.data}
                      </pre>
                    </div>
                  </div>
                )}

                {!selectedPing.data && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Data</label>
                    <p className="mt-1 text-sm text-gray-500 italic">No data provided with this ping</p>
                  </div>
                )}
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setSelectedPing(null)}
                  className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}