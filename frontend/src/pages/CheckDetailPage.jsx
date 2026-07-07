import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Copy, Pause, Play, Clock, Activity as ActivityIcon, Bell, Users, CheckCircle, Settings } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { config } from '../config'
import { useToast } from '../components/Toast'
import ConfirmDialog from '../components/ConfirmDialog'
import DurationInput from '../components/DurationInput'

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

function slugPingUrl(baseUrl, teamSlug, checkSlug) {
  return `${baseUrl}/ping/${teamSlug}/${checkSlug}`
}

function toDateTimeLocalValue(date) {
  const offsetMilliseconds = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMilliseconds).toISOString().slice(0, 16)
}

function createDefaultUptimeRange() {
  const now = new Date()
  const dayAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000))
  return {
    startAt: toDateTimeLocalValue(dayAgo),
    endAt: toDateTimeLocalValue(now),
  }
}

function createDefaultMaintenanceForm() {
  const startAt = new Date()
  const endAt = new Date(startAt.getTime() + (60 * 60 * 1000))
  return {
    scope: 'check',
    startAt: toDateTimeLocalValue(startAt),
    endAt: toDateTimeLocalValue(endAt),
    label: '',
  }
}

export default function CheckDetailPage({ user, onLogout }) {
  const { teamId, checkId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [check, setCheck] = useState(null)
  const [pings, setPings] = useState([])
  const [stats, setStats] = useState(null)
  const [statsRange, setStatsRange] = useState('24h')
  const [statsLoading, setStatsLoading] = useState(false)
  const [errorSummary, setErrorSummary] = useState(null)
  const [errorRange, setErrorRange] = useState('24h')
  const [errorsLoading, setErrorsLoading] = useState(false)
  const [uptimeReport, setUptimeReport] = useState(null)
  const [uptimeLoading, setUptimeLoading] = useState(false)
  const [uptimeRange, setUptimeRange] = useState(() => createDefaultUptimeRange())
  const [excludeMaintenance, setExcludeMaintenance] = useState(true)
  const [maintenanceWindows, setMaintenanceWindows] = useState([])
  const [maintenanceLoading, setMaintenanceLoading] = useState(false)
  const [maintenanceSaving, setMaintenanceSaving] = useState(false)
  const [maintenanceForm, setMaintenanceForm] = useState(() => createDefaultMaintenanceForm())
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const [selectedPing, setSelectedPing] = useState(null)
  const [showTokenRotated, setShowTokenRotated] = useState(false)
  const [confirmState, setConfirmState] = useState(null)
  const [alertHistory, setAlertHistory] = useState([])
  const [escalationForm, setEscalationForm] = useState({ escalationMinutes: 0, escalationAlertChannels: [], suppressAfterCount: 0, suppressDurationMinutes: 0 })
  const [savingEscalation, setSavingEscalation] = useState(false)
  const [availableTopics, setAvailableTopics] = useState([])
  const [availableChannels, setAvailableChannels] = useState([])
  const [teamSlug, setTeamSlug] = useState(null)
  const [showAlertSettings, setShowAlertSettings] = useState(false)
  const [showEditHttpCheck, setShowEditHttpCheck] = useState(false)
  const [editHttpData, setEditHttpData] = useState({ url: '', expectedStatusCode: 200, expectedString: '', failureThreshold: 1 })
  const [editHttpLoading, setEditHttpLoading] = useState(false)
  const [editingPeriod, setEditingPeriod] = useState(false)
  const [editingGrace, setEditingGrace] = useState(false)
  const [editPeriodSeconds, setEditPeriodSeconds] = useState(null)
  const [editGraceSeconds, setEditGraceSeconds] = useState(null)
  const [savingPeriod, setSavingPeriod] = useState(false)
  const [savingGrace, setSavingGrace] = useState(false)

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

  useEffect(() => {
    if (check?.type === 'http') {
      loadCheckStats(statsRange)
    } else {
      setStats(null)
    }
  }, [teamId, checkId, check?.type, statsRange])

  useEffect(() => {
    if (check) {
      loadCheckErrorSummary(errorRange)
    } else {
      setErrorSummary(null)
    }
  }, [teamId, checkId, check?.checkId, errorRange])

  useEffect(() => {
    if (check) {
      loadCheckUptime(uptimeRange.startAt, uptimeRange.endAt, excludeMaintenance)
      loadMaintenanceWindows()
    } else {
      setUptimeReport(null)
      setMaintenanceWindows([])
    }
  }, [teamId, checkId, check?.checkId])

  async function loadCheckData() {
    try {
      const [checkData, pingsData, teamData] = await Promise.all([
        api.getCheck(teamId, checkId),
        api.listPings(teamId, checkId, 20),
        api.getTeam(teamId),
      ])
      if (teamData?.slug) setTeamSlug(teamData.slug)
      // Construct pingUrl from token if not provided by backend
      if (checkData.token && !checkData.pingUrl) {
        checkData.pingUrl = `${getPingBaseUrl()}/ping/${checkData.token}`
      }
      setCheck(checkData)
      setEscalationForm({
        escalationMinutes: checkData.escalationMinutes || 0,
        escalationAlertChannels: checkData.escalationAlertChannels || [],
        suppressAfterCount: checkData.suppressAfterCount || 0,
        suppressDurationMinutes: checkData.suppressDurationMinutes || 0,
      })
      // Backend returns array directly, not wrapped in {pings: [...]}
      setPings(Array.isArray(pingsData) ? pingsData : pingsData.pings || [])
    } catch {
    } finally {
      setLoading(false)
    }
    loadAlertHistory()
  }

  async function loadAlertHistory() {
    try {
      const history = await api.getCheckAlertHistory(teamId, checkId, 25)
      setAlertHistory(Array.isArray(history) ? history : [])
    } catch {
      setAlertHistory([])
    }
  }

  async function loadCheckStats(range) {
    setStatsLoading(true)
    try {
      const statsData = await api.getCheckStats(teamId, checkId, range)
      setStats(statsData)
    } catch {
      setStats(null)
    } finally {
      setStatsLoading(false)
    }
  }

  async function loadCheckErrorSummary(range) {
    setErrorsLoading(true)
    try {
      const errorData = await api.getCheckErrorSummary(teamId, checkId, range)
      setErrorSummary(errorData)
    } catch {
      setErrorSummary(null)
    } finally {
      setErrorsLoading(false)
    }
  }

  async function loadCheckUptime(startAt, endAt, exclude) {
    setUptimeLoading(true)
    try {
      const uptimeData = await api.getCheckUptime(
        teamId,
        checkId,
        new Date(startAt).toISOString(),
        new Date(endAt).toISOString(),
        exclude,
      )
      setUptimeReport(uptimeData)
    } catch {
      setUptimeReport(null)
    } finally {
      setUptimeLoading(false)
    }
  }

  async function loadMaintenanceWindows() {
    setMaintenanceLoading(true)
    try {
      const windows = await api.listMaintenanceWindows(teamId, checkId)
      setMaintenanceWindows(Array.isArray(windows) ? windows : [])
    } catch {
      setMaintenanceWindows([])
    } finally {
      setMaintenanceLoading(false)
    }
  }

  async function handleApplyUptimeReport() {
    await loadCheckUptime(uptimeRange.startAt, uptimeRange.endAt, excludeMaintenance)
  }

  async function handleCreateMaintenanceWindow(event) {
    event.preventDefault()
    setMaintenanceSaving(true)
    try {
      await api.createMaintenanceWindow(teamId, {
        checkId: maintenanceForm.scope === 'team' ? undefined : checkId,
        startAt: new Date(maintenanceForm.startAt).toISOString(),
        endAt: new Date(maintenanceForm.endAt).toISOString(),
        label: maintenanceForm.label || undefined,
      })
      setMaintenanceForm(createDefaultMaintenanceForm())
      await Promise.all([
        loadMaintenanceWindows(),
        loadCheckUptime(uptimeRange.startAt, uptimeRange.endAt, excludeMaintenance),
      ])
      toast.success('Maintenance window saved')
    } catch (error) {
      toast.error('Failed to save maintenance window: ' + error.message)
    } finally {
      setMaintenanceSaving(false)
    }
  }

  async function handleDeleteMaintenanceWindow(windowId) {
    try {
      await api.deleteMaintenanceWindow(teamId, windowId)
      await Promise.all([
        loadMaintenanceWindows(),
        loadCheckUptime(uptimeRange.startAt, uptimeRange.endAt, excludeMaintenance),
      ])
      toast.success('Maintenance window deleted')
    } catch (error) {
      toast.error('Failed to delete maintenance window: ' + error.message)
    }
  }

  async function loadAlertTopics() {
    try {
      const channels = await api.listAlertChannels(teamId)
      setAvailableTopics(Array.isArray(channels) ? channels : [])
    } catch {
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
        } catch {
          continue
        }
      }

      // Combine team channels and shared channels
      const allChannels = [
        ...(Array.isArray(teamChannels) ? teamChannels : []),
        ...sharedChannels
      ]

      setAvailableChannels(allChannels)
    } catch {
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
      toast.error('Failed to update alert channels: ' + error.message)
      // Revert on error
      loadCheckData()
    }
  }

  async function handleSaveEscalation() {
    setSavingEscalation(true)
    try {
      const updated = await api.updateCheck(teamId, checkId, {
        escalationMinutes: escalationForm.escalationMinutes,
        escalationAlertChannels: escalationForm.escalationAlertChannels,
        suppressAfterCount: escalationForm.suppressAfterCount,
        suppressDurationMinutes: escalationForm.suppressDurationMinutes,
      })
      setCheck(updated)
      toast.success('Escalation settings saved')
    } catch (error) {
      toast.error('Failed to save escalation settings: ' + error.message)
    } finally {
      setSavingEscalation(false)
    }
  }

  async function handlePause() {
    try {
      await api.pauseCheck(teamId, checkId)
      loadCheckData()
    } catch (error) {
      toast.error('Failed to pause check: ' + error.message)
    }
  }

  async function handleResume() {
    try {
      await api.resumeCheck(teamId, checkId)
      loadCheckData()
    } catch (error) {
      toast.error('Failed to resume check: ' + error.message)
    }
  }

  function handleRotateToken() {
    setConfirmState({
      title: 'Rotate Token',
      message: 'Are you sure you want to rotate the token? The old ping URL will stop working immediately.',
      confirmLabel: 'Rotate Token',
      onConfirm: async () => {
        try {
          const updatedCheck = await api.rotateCheckToken(teamId, checkId)
          // Update check with new token and ping URL
          updatedCheck.pingUrl = `${getPingBaseUrl()}/ping/${updatedCheck.token}`
          setCheck(updatedCheck)
          setShowTokenRotated(true)
          toast.success('Token rotated successfully')
        } catch (error) {
          toast.error('Failed to rotate token: ' + error.message)
        }
      },
    })
  }

  function handleDeleteCheck() {
    setConfirmState({
      title: 'Delete Check',
      message: `Are you sure you want to delete "${check.name}"? This action cannot be undone and will delete all ping history.`,
      confirmLabel: 'Delete',
      destructive: true,
      onConfirm: async () => {
        try {
          await api.deleteCheck(teamId, checkId)
          toast.success('Check deleted successfully')
          navigate(`/teams/${teamId}/checks`)
        } catch (error) {
          toast.error('Failed to delete check: ' + error.message)
        }
      },
    })
  }

  function openEditHttpCheck() {
    setEditHttpData({
      url: check.url || '',
      expectedStatusCode: check.expectedStatusCode || 200,
      expectedString: check.expectedString || '',
      failureThreshold: check.failureThreshold || 1,
    })
    setShowEditHttpCheck(true)
  }

  async function handleSavePeriod() {
    setSavingPeriod(true)
    try {
      const updated = await api.updateCheck(teamId, checkId, { periodSeconds: editPeriodSeconds })
      setCheck(updated)
      setEditingPeriod(false)
      toast.success('Period updated')
    } catch (error) {
      toast.error('Failed to update period: ' + error.message)
    } finally {
      setSavingPeriod(false)
    }
  }

  async function handleSaveGrace() {
    setSavingGrace(true)
    try {
      const updated = await api.updateCheck(teamId, checkId, { graceSeconds: editGraceSeconds })
      setCheck(updated)
      setEditingGrace(false)
      toast.success('Grace period updated')
    } catch (error) {
      toast.error('Failed to update grace period: ' + error.message)
    } finally {
      setSavingGrace(false)
    }
  }

  async function handleEditHttpCheck(e) {
    e.preventDefault()
    setEditHttpLoading(true)
    try {
      const payload = {
        url: editHttpData.url,
        expectedStatusCode: editHttpData.expectedStatusCode,
        failureThreshold: editHttpData.failureThreshold,
      }
      if (editHttpData.expectedString) payload.expectedString = editHttpData.expectedString
      const updatedCheck = await api.updateCheck(teamId, checkId, payload)
      setCheck(updatedCheck)
      setShowEditHttpCheck(false)
      toast.success('HTTP check updated successfully')
    } catch (error) {
      toast.error('Failed to update check: ' + error.message)
    } finally {
      setEditHttpLoading(false)
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

  function formatResponseTime(value) {
    return value == null ? 'N/A' : `${value} ms`
  }

  function formatFailureCode(value) {
    return value || 'unknown'
  }

  function formatIncidentDuration(value) {
    if (value == null) return 'N/A'
    if (value < 60) return `${value}s`
    if (value < 3600) return `${Math.round(value / 60)}m`
    return `${(value / 3600).toFixed(1)}h`
  }

  function formatMinutes(value) {
    return value == null ? '0 min' : `${value} min`
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
              <span className="ml-3 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 capitalize">
                {check.type || 'cron'}
              </span>
            </p>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
              {check.type !== 'http' && (
              <div className="sm:col-span-2 space-y-4">
                {/* Token-based URL */}
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center justify-between">
                    <span>Ping URL <span className="text-xs text-gray-400 font-normal">(token-based)</span></span>
                    <button
                      onClick={handleRotateToken}
                      className="inline-flex items-center px-2 py-1 border border-red-200 text-xs font-medium rounded text-red-600 bg-white hover:bg-red-50"
                      title="Rotate Token (invalidates current URL)"
                    >
                      🔄 Rotate token
                    </button>
                  </dt>
                  <dd className="mt-1 flex items-center space-x-2">
                    <code className="flex-1 text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded border border-gray-200 overflow-x-auto">
                      {check.pingUrl}
                    </code>
                    <button onClick={copyPingUrl} className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50" title="Copy">
                      <Copy className="h-4 w-4" />
                    </button>
                  </dd>
                  {copied && <p className="mt-1 text-xs text-green-600">Copied!</p>}
                </div>

                {/* Slug-based URL */}
                {check.slug && teamSlug && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">
                      Ping URL <span className="text-xs text-gray-400 font-normal">(name-based)</span>
                    </dt>
                    <dd className="mt-1 flex items-center space-x-2">
                      <code className="flex-1 text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded border border-gray-200 overflow-x-auto">
                        {slugPingUrl(getPingBaseUrl(), teamSlug, check.slug)}
                      </code>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(slugPingUrl(getPingBaseUrl(), teamSlug, check.slug))
                          toast.success('Slug URL copied!')
                        }}
                        className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                        title="Copy slug URL"
                      >
                        <Copy className="h-4 w-4" />
                      </button>
                    </dd>
                    <p className="mt-1 text-xs text-gray-500">
                      Defaults to success. Supports the same actions as the token URL: <code className="bg-gray-100 px-1 rounded">/fail</code>, <code className="bg-gray-100 px-1 rounded">/start</code>, <code className="bg-gray-100 px-1 rounded">/500</code>, etc.
                    </p>
                  </div>
                )}

                {check.type === 'heartbeat' && (
                  <p className="text-xs text-gray-500">Heartbeat — send a GET or POST at each interval. /start and /fail are not supported.</p>
                )}
                {check.type === 'cron' && (
                  <p className="text-xs text-gray-500">Cron job — optionally ping <code className="bg-gray-100 px-1 rounded">/start</code> when the job begins and <code className="bg-gray-100 px-1 rounded">/fail</code> if it fails.</p>
                )}
              </div>
              )}

              {check.type === 'http' && (
              <div className="sm:col-span-2">
                <dt className="text-sm font-medium text-gray-500 flex items-center justify-between">
                  <span>Monitored URL</span>
                  <button
                    onClick={openEditHttpCheck}
                    className="inline-flex items-center px-2 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <Settings className="h-3 w-3 mr-1" />
                    Edit
                  </button>
                </dt>
                <dd className="mt-1 text-sm text-gray-900 bg-gray-50 px-3 py-2 rounded border border-gray-200 overflow-x-auto">
                  {check.url} <span className="text-gray-500">(expecting {check.expectedStatusCode || 200})</span>
                </dd>
              </div>
              )}

              <div>
                <dt className="text-sm font-medium text-gray-500 flex items-center justify-between">
                  <span className="flex items-center"><Clock className="h-4 w-4 mr-1" />Period</span>
                  {!editingPeriod && (
                    <button
                      onClick={() => { setEditPeriodSeconds(check.periodSeconds); setEditingPeriod(true) }}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                  )}
                </dt>
                <dd className="mt-1">
                  {editingPeriod ? (
                    <div className="flex items-center gap-2">
                      <DurationInput
                        key={`detail-period-${check.checkId}`}
                        value={editPeriodSeconds}
                        onChange={setEditPeriodSeconds}
                        min={60}
                        required
                      />
                      <button
                        onClick={handleSavePeriod}
                        disabled={savingPeriod}
                        className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {savingPeriod ? '...' : 'Save'}
                      </button>
                      <button
                        onClick={() => setEditingPeriod(false)}
                        className="text-xs px-2 py-1 border border-gray-300 rounded text-gray-600 hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <span className="text-sm text-gray-900">{formatDuration(check.periodSeconds)}</span>
                  )}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500 flex items-center justify-between">
                  <span className="flex items-center"><Clock className="h-4 w-4 mr-1" />Grace Period</span>
                  {!editingGrace && (
                    <button
                      onClick={() => { setEditGraceSeconds(check.graceSeconds); setEditingGrace(true) }}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Edit
                    </button>
                  )}
                </dt>
                <dd className="mt-1">
                  {editingGrace ? (
                    <div className="flex items-center gap-2">
                      <DurationInput
                        key={`detail-grace-${check.checkId}`}
                        value={editGraceSeconds}
                        onChange={setEditGraceSeconds}
                        min={0}
                        required
                      />
                      <button
                        onClick={handleSaveGrace}
                        disabled={savingGrace}
                        className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {savingGrace ? '...' : 'Save'}
                      </button>
                      <button
                        onClick={() => setEditingGrace(false)}
                        className="text-xs px-2 py-1 border border-gray-300 rounded text-gray-600 hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <span className="text-sm text-gray-900">{formatDuration(check.graceSeconds)}</span>
                  )}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500">{check.type === 'http' ? 'Last Checked' : 'Last Ping'}</dt>
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
            {check.graceSeconds > 2 * check.periodSeconds && (
              <div className="mt-4 bg-amber-50 border border-amber-300 rounded-md p-3 text-sm text-amber-800">
                ⚠️ Grace period is longer than 2× the check period — you may miss alerts
              </div>
            )}
          </div>
        </div>

        {check.type === 'http' && (
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg leading-6 font-medium text-gray-900">Performance History</h3>
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  Response time and availability statistics for recent HTTP polls
                </p>
              </div>
              <select
                aria-label="Stats range"
                value={statsRange}
                onChange={(event) => setStatsRange(event.target.value)}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
              >
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
            </div>
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              {statsLoading ? (
                <div className="text-sm text-gray-500">Loading performance statistics...</div>
              ) : !stats ? (
                <div className="text-sm text-gray-500">Performance statistics are not available yet.</div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Uptime</div>
                      <div className="mt-2 text-2xl font-semibold text-gray-900">{stats.uptimePct}%</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Average</div>
                      <div className="mt-2 text-2xl font-semibold text-gray-900">{formatResponseTime(stats.avgResponseMs)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">P95</div>
                      <div className="mt-2 text-2xl font-semibold text-gray-900">{formatResponseTime(stats.p95ResponseMs)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Latest</div>
                      <div className="mt-2 text-2xl font-semibold text-gray-900">{formatResponseTime(stats.latestResponseMs)}</div>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Failures</div>
                      <div className="mt-2 text-2xl font-semibold text-gray-900">{stats.failCount}</div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Recent response samples</h4>
                    {stats.responseTimeSeries.length === 0 ? (
                      <div className="mt-2 text-sm text-gray-500">No response-time data recorded for this window.</div>
                    ) : (
                      <div className="mt-3 overflow-hidden rounded-md border border-gray-200">
                        <ul className="divide-y divide-gray-200">
                          {stats.responseTimeSeries.slice(-10).reverse().map((point) => (
                            <li key={`${point.timestamp}-${point.responseTimeMs}`} className="flex items-center justify-between px-4 py-3 text-sm">
                              <div>
                                <div className="font-medium text-gray-900">{point.responseTimeMs} ms</div>
                                <div className="text-xs text-gray-500">{formatDistanceToNow(new Date(point.timestamp), { addSuffix: true })}</div>
                              </div>
                              <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
                                point.pingType === 'fail' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                              }`}>
                                {point.pingType}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex items-start justify-between gap-4">
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Error Analysis</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Failure trends, dominant error reasons, and the latest failure log for this check
              </p>
            </div>
            <select
              aria-label="Error range"
              value={errorRange}
              onChange={(event) => setErrorRange(event.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
            >
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            {errorsLoading ? (
              <div className="text-sm text-gray-500">Loading error summary...</div>
            ) : !errorSummary ? (
              <div className="text-sm text-gray-500">Error summary is not available yet.</div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Failures</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{errorSummary.totalFailures}</div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Most Common Code</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{formatFailureCode(errorSummary.mostCommonCode)}</div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Last Failure</div>
                    <div className="mt-2 text-sm font-semibold text-gray-900">
                      {errorSummary.lastFailureAt ? formatDistanceToNow(new Date(errorSummary.lastFailureAt), { addSuffix: true }) : 'No failures'}
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Longest Incident</div>
                    <div className="mt-2 text-sm font-semibold text-gray-900">
                      {errorSummary.longestIncident ? formatIncidentDuration(errorSummary.longestIncident.durationSeconds) : 'No incidents'}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Failure codes</h4>
                    {errorSummary.failureCodes.length === 0 ? (
                      <div className="mt-2 text-sm text-gray-500">No failures recorded for this window.</div>
                    ) : (
                      <div className="mt-3 overflow-hidden rounded-md border border-gray-200">
                        <ul className="divide-y divide-gray-200">
                          {errorSummary.failureCodes.map((entry) => (
                            <li key={entry.code} className="flex items-center justify-between px-4 py-3 text-sm">
                              <div className="font-medium text-gray-900">{formatFailureCode(entry.code)}</div>
                              <div className="text-gray-500">{entry.count} event{entry.count === 1 ? '' : 's'}</div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Recent failures</h4>
                    {errorSummary.recentFailures.length === 0 ? (
                      <div className="mt-2 text-sm text-gray-500">No recent failures recorded.</div>
                    ) : (
                      <div className="mt-3 overflow-hidden rounded-md border border-gray-200">
                        <ul className="divide-y divide-gray-200">
                          {errorSummary.recentFailures.map((ping) => (
                            <li key={`${ping.timestamp}-${ping.code || 'failure'}`} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                              <div>
                                <div className="font-medium text-gray-900">{formatFailureCode(ping.code)}</div>
                                <div className="text-xs text-gray-500">{formatDistanceToNow(new Date(ping.receivedAt), { addSuffix: true })}</div>
                                {ping.data && (
                                  <div className="mt-1 text-xs text-gray-600 line-clamp-2">{ping.data}</div>
                                )}
                              </div>
                              <div className="text-right">
                                <div className="text-sm font-medium text-gray-900">{formatResponseTime(ping.responseTimeMs)}</div>
                                <button
                                  onClick={() => setSelectedPing(ping)}
                                  className="mt-1 text-xs text-blue-600 hover:text-blue-800"
                                >
                                  View payload
                                </button>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Uptime Report</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Calculate uptime across a custom window and exclude scheduled maintenance from the result.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="text-sm text-gray-600">
                <span className="mb-1 block font-medium text-gray-700">From</span>
                <input
                  type="datetime-local"
                  value={uptimeRange.startAt}
                  onChange={(event) => setUptimeRange((current) => ({ ...current, startAt: event.target.value }))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                />
              </label>
              <label className="text-sm text-gray-600">
                <span className="mb-1 block font-medium text-gray-700">To</span>
                <input
                  type="datetime-local"
                  value={uptimeRange.endAt}
                  onChange={(event) => setUptimeRange((current) => ({ ...current, endAt: event.target.value }))}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                />
              </label>
              <label className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-700 lg:mt-6">
                <input
                  type="checkbox"
                  checked={excludeMaintenance}
                  onChange={(event) => setExcludeMaintenance(event.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Exclude maintenance
              </label>
              <button
                onClick={handleApplyUptimeReport}
                disabled={uptimeLoading}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 lg:mt-6"
              >
                {uptimeLoading ? 'Running...' : 'Run report'}
              </button>
            </div>
          </div>
          <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
            {uptimeLoading ? (
              <div className="text-sm text-gray-500">Calculating uptime...</div>
            ) : !uptimeReport ? (
              <div className="text-sm text-gray-500">Uptime reporting is not available yet for this window.</div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Uptime</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{uptimeReport.uptimePct}%</div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Observed Minutes</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{formatMinutes(uptimeReport.totalObservedMinutes)}</div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Downtime</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{formatMinutes(uptimeReport.downtimeMinutes)}</div>
                  </div>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Excluded Maintenance</div>
                    <div className="mt-2 text-2xl font-semibold text-gray-900">{formatMinutes(uptimeReport.excludedMaintenanceMinutes)}</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Incident Timeline</h4>
                    {uptimeReport.incidents.length === 0 ? (
                      <div className="mt-2 text-sm text-gray-500">No downtime incidents were recorded for this window.</div>
                    ) : (
                      <div className="mt-3 overflow-hidden rounded-md border border-gray-200">
                        <ul className="divide-y divide-gray-200">
                          {uptimeReport.incidents.map((incident) => (
                            <li key={`${incident.startedAt}-${incident.endedAt}`} className="px-4 py-3 text-sm">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <div className="font-medium text-gray-900">{formatFailureCode(incident.dominantCode)}</div>
                                  <div className="text-xs text-gray-500">
                                    {new Date(incident.startedAt).toLocaleString()} to {new Date(incident.endedAt).toLocaleString()}
                                  </div>
                                </div>
                                <div className="text-right">
                                  <div className="font-medium text-gray-900">{formatIncidentDuration(incident.durationSeconds)}</div>
                                  <div className="text-xs text-gray-500">{incident.failureCount} failure sample{incident.failureCount === 1 ? '' : 's'}</div>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex items-center justify-between gap-4">
                      <h4 className="text-sm font-medium text-gray-700">Maintenance Windows</h4>
                      {maintenanceLoading && <span className="text-xs text-gray-500">Refreshing...</span>}
                    </div>
                    <form onSubmit={handleCreateMaintenanceWindow} className="mt-3 grid gap-3 rounded-md border border-gray-200 p-4 sm:grid-cols-2">
                      <label className="text-sm text-gray-600 sm:col-span-2">
                        <span className="mb-1 block font-medium text-gray-700">Applies To</span>
                        <select
                          value={maintenanceForm.scope}
                          onChange={(event) => setMaintenanceForm((current) => ({ ...current, scope: event.target.value }))}
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                        >
                          <option value="check">This check only</option>
                          <option value="team">Entire team</option>
                        </select>
                      </label>
                      <label className="text-sm text-gray-600">
                        <span className="mb-1 block font-medium text-gray-700">Start</span>
                        <input
                          type="datetime-local"
                          value={maintenanceForm.startAt}
                          onChange={(event) => setMaintenanceForm((current) => ({ ...current, startAt: event.target.value }))}
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                          required
                        />
                      </label>
                      <label className="text-sm text-gray-600">
                        <span className="mb-1 block font-medium text-gray-700">End</span>
                        <input
                          type="datetime-local"
                          value={maintenanceForm.endAt}
                          onChange={(event) => setMaintenanceForm((current) => ({ ...current, endAt: event.target.value }))}
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                          required
                        />
                      </label>
                      <label className="text-sm text-gray-600 sm:col-span-2">
                        <span className="mb-1 block font-medium text-gray-700">Label</span>
                        <input
                          type="text"
                          value={maintenanceForm.label}
                          onChange={(event) => setMaintenanceForm((current) => ({ ...current, label: event.target.value }))}
                          placeholder="Deploy, migration, vendor maintenance..."
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700"
                        />
                      </label>
                      <div className="sm:col-span-2">
                        <button
                          type="submit"
                          disabled={maintenanceSaving}
                          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
                        >
                          {maintenanceSaving ? 'Saving...' : 'Add maintenance window'}
                        </button>
                        <div className="mt-2 text-xs text-gray-500">
                          {maintenanceForm.scope === 'team'
                            ? 'This window will be excluded from uptime reports across the whole team.'
                            : 'This window will only be excluded for the current check.'}
                        </div>
                      </div>
                    </form>

                    {maintenanceWindows.length === 0 ? (
                      <div className="mt-3 text-sm text-gray-500">No maintenance windows scheduled for this check.</div>
                    ) : (
                      <div className="mt-3 overflow-hidden rounded-md border border-gray-200">
                        <ul className="divide-y divide-gray-200">
                          {maintenanceWindows.map((window) => (
                            <li key={window.windowId} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                              <div>
                                <div className="font-medium text-gray-900">{window.label || 'Scheduled maintenance'}</div>
                                <div className="text-xs text-gray-500">
                                  {new Date(window.startAt).toLocaleString()} to {new Date(window.endAt).toLocaleString()}
                                </div>
                                <div className="mt-1 text-xs text-gray-500">
                                  {window.checkId ? 'Scope: this check' : 'Scope: entire team'}
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleDeleteMaintenanceWindow(window.windowId)}
                                className="text-xs font-medium text-red-600 hover:text-red-800"
                              >
                                Delete
                              </button>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Unified Alert Configuration */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
                <Bell className="h-5 w-5 mr-2" />
                Alert Configuration
                {(check.alertChannels || []).length > 0 ? (
                  <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    {check.alertChannels.length} {check.alertChannels.length === 1 ? 'channel' : 'channels'} active
                  </span>
                ) : (
                  <span className="ml-3 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                    ⚠ No channels — alerts disabled
                  </span>
                )}
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

                {/* Escalation & Suppression */}
                <div className="border-t border-gray-200 pt-4">
                  <div className="text-sm font-medium text-gray-700 mb-1">Escalation</div>
                  <p className="text-sm text-gray-500 mb-3">
                    If the check stays late, notify additional channels after a delay. Set to 0 to disable.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="escalationMinutes" className="block text-sm text-gray-700">Escalate after (minutes)</label>
                      <input
                        type="number"
                        id="escalationMinutes"
                        min="0"
                        max="1440"
                        value={escalationForm.escalationMinutes}
                        onChange={(e) => setEscalationForm({ ...escalationForm, escalationMinutes: parseInt(e.target.value) || 0 })}
                        className="mt-1 block w-32 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <span className="block text-sm text-gray-700 mb-1">Escalation channels</span>
                      {availableChannels.length === 0 ? (
                        <p className="text-sm text-gray-500">No channels available</p>
                      ) : (
                        <div className="space-y-1 max-h-32 overflow-y-auto">
                          {availableChannels.map((channel) => (
                            <label key={channel.channelId} className="flex items-center">
                              <input
                                type="checkbox"
                                checked={escalationForm.escalationAlertChannels.includes(channel.channelId)}
                                onChange={(e) => {
                                  const current = escalationForm.escalationAlertChannels
                                  setEscalationForm({
                                    ...escalationForm,
                                    escalationAlertChannels: e.target.checked
                                      ? [...current, channel.channelId]
                                      : current.filter(id => id !== channel.channelId),
                                  })
                                }}
                                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                              />
                              <span className="ml-2 text-sm text-gray-900">{channel.displayName} ({channel.type.toUpperCase()})</span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="text-sm font-medium text-gray-700 mt-5 mb-1">Alert suppression</div>
                  <p className="text-sm text-gray-500 mb-3">
                    Mute repeat alerts after N consecutive notifications. Set to 0 to disable.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="suppressAfterCount" className="block text-sm text-gray-700">Suppress after (alerts)</label>
                      <input
                        type="number"
                        id="suppressAfterCount"
                        min="0"
                        max="100"
                        value={escalationForm.suppressAfterCount}
                        onChange={(e) => setEscalationForm({ ...escalationForm, suppressAfterCount: parseInt(e.target.value) || 0 })}
                        className="mt-1 block w-32 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="suppressDurationMinutes" className="block text-sm text-gray-700">Suppress for (minutes)</label>
                      <input
                        type="number"
                        id="suppressDurationMinutes"
                        min="0"
                        max="10080"
                        value={escalationForm.suppressDurationMinutes}
                        onChange={(e) => setEscalationForm({ ...escalationForm, suppressDurationMinutes: parseInt(e.target.value) || 0 })}
                        className="mt-1 block w-32 border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                      />
                    </div>
                  </div>

                  {check?.suppressedUntil && new Date(check.suppressedUntil) > new Date() && (
                    <div className="mt-3 p-3 bg-amber-50 rounded-md text-sm text-amber-800">
                      Alerts currently suppressed until {new Date(check.suppressedUntil).toLocaleString()}
                    </div>
                  )}

                  <button
                    onClick={handleSaveEscalation}
                    disabled={savingEscalation}
                    className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {savingEscalation ? 'Saving…' : 'Save escalation settings'}
                  </button>
                </div>

              </div>
            </div>
          )}
        </div>

        {/* Alert Delivery History */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
              <Bell className="h-5 w-5 mr-2" />
              Alert History
            </h3>
            <p className="mt-1 max-w-2xl text-sm text-gray-500">
              Every notification sent (or attempted) for this check
            </p>
          </div>
          <div className="border-t border-gray-200">
            {alertHistory.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No alerts sent yet — that's a good sign
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {alertHistory.map((entry) => (
                  <li key={entry.deliveryId} className="px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          entry.alertType === 'recovery'
                            ? 'bg-green-100 text-green-800'
                            : entry.alertType === 'escalation'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-red-100 text-red-800'
                        }`}>
                          {entry.alertType.toUpperCase()}
                        </span>
                        <span className="text-sm text-gray-900">
                          {entry.channelName}
                          <span className="ml-1 text-gray-500">({entry.channelType})</span>
                        </span>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          entry.status === 'delivered'
                            ? 'bg-green-100 text-green-800'
                            : entry.status === 'pending'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-red-100 text-red-800'
                        }`}>
                          {entry.status === 'pending' ? `RETRYING (${entry.attempts}/${entry.maxAttempts})` : entry.status.toUpperCase()}
                        </span>
                        <span className="text-sm text-gray-500" title={new Date(entry.createdAt).toLocaleString()}>
                          {formatDistanceToNow(new Date(entry.createdAt), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                    {entry.status === 'failed' && entry.lastError && (
                      <p className="mt-1 text-xs text-red-600">
                        Failed after {entry.attempts} {entry.attempts === 1 ? 'attempt' : 'attempts'}: {entry.lastError}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
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
                        <div className="flex items-center space-x-2">
                          <p className="text-sm text-gray-900">
                            {formatDistanceToNow(new Date(ping.receivedAt), { addSuffix: true })}
                          </p>
                          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                            ping.ping_type === 'fail' ? 'bg-red-100 text-red-800' :
                            ping.ping_type === 'start' ? 'bg-blue-100 text-blue-800' :
                            'bg-green-100 text-green-800'
                          }`}>
                            {ping.ping_type}
                          </span>
                        </div>
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

        {check.type !== 'http' && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <h4 className="text-sm font-medium text-blue-900 mb-2">Usage Example</h4>
          <pre className="text-xs text-blue-800 bg-white p-3 rounded border border-blue-200 overflow-x-auto">
            {`# Token-based URL (secure)
curl ${check.pingUrl}${check.slug && teamSlug ? `

# Name-based URL (easier to read in scripts)
curl ${slugPingUrl(getPingBaseUrl(), teamSlug, check.slug)}` : ''}

# With data
curl -X POST ${check.pingUrl} \\
  -H "Content-Type: application/json" \\
  -d "{\\"data\\": \\"Backup completed: 1.2GB\\"}"

# Record failure
curl -X POST ${check.pingUrl}/fail

# Record job start
curl ${check.pingUrl}/start`}
          </pre>
        </div>
        )}
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

      {/* Token Rotated Modal */}
      {showTokenRotated && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mt-4">Token Rotated</h3>
              <div className="mt-2 px-7 py-3">
                <p className="text-sm text-gray-500 mb-3">
                  Your new ping URL is:
                </p>
                <div className="bg-gray-50 rounded-md p-3 mb-3">
                  <code className="text-xs text-gray-700 break-all block">
                    {check?.pingUrl}
                  </code>
                </div>
                <p className="text-xs text-gray-500">
                  Please update your monitoring scripts with this new URL.
                </p>
              </div>
              <div className="items-center px-4 py-3">
                <button
                  onClick={() => setShowTokenRotated(false)}
                  className="px-4 py-2 bg-blue-600 text-white text-base font-medium rounded-md w-full shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit HTTP Check Modal */}
      {showEditHttpCheck && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-11/12 md:w-1/2 lg:w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-gray-900">Edit HTTP Check</h3>
                <button onClick={() => setShowEditHttpCheck(false)} className="text-gray-400 hover:text-gray-600">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <form onSubmit={handleEditHttpCheck} className="space-y-4">
                <div>
                  <label htmlFor="editUrl" className="block text-sm font-medium text-gray-700">URL</label>
                  <input
                    type="url"
                    id="editUrl"
                    value={editHttpData.url}
                    onChange={(e) => setEditHttpData({ ...editHttpData, url: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="https://example.com/health"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="editStatusCode" className="block text-sm font-medium text-gray-700">Expected Status Code</label>
                  <input
                    type="number"
                    id="editStatusCode"
                    value={editHttpData.expectedStatusCode}
                    onChange={(e) => setEditHttpData({ ...editHttpData, expectedStatusCode: parseInt(e.target.value) || 200 })}
                    className="mt-1 block w-32 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    min="100"
                    max="599"
                  />
                </div>
                <div>
                  <label htmlFor="editExpectedString" className="block text-sm font-medium text-gray-700">Expected String <span className="text-gray-400 font-normal">(optional)</span></label>
                  <input
                    type="text"
                    id="editExpectedString"
                    value={editHttpData.expectedString}
                    onChange={(e) => setEditHttpData({ ...editHttpData, expectedString: e.target.value })}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="OK"
                  />
                </div>
                <div>
                  <label htmlFor="editFailureThreshold" className="block text-sm font-medium text-gray-700">Alert after N consecutive failures</label>
                  <input
                    type="number"
                    id="editFailureThreshold"
                    value={editHttpData.failureThreshold}
                    onChange={(e) => setEditHttpData({ ...editHttpData, failureThreshold: parseInt(e.target.value) || 1 })}
                    className="mt-1 block w-32 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    min="1"
                    max="100"
                  />
                </div>
                <div className="flex space-x-3 pt-2">
                  <button
                    type="submit"
                    disabled={editHttpLoading}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
                  >
                    {editHttpLoading ? 'Saving...' : 'Save Changes'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowEditHttpCheck(false)}
                    disabled={editHttpLoading}
                    className="flex-1 px-4 py-2 bg-white text-gray-500 text-sm font-medium rounded-md shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
      <ConfirmDialog state={confirmState} onClose={() => setConfirmState(null)} />
    </Layout>
  )
}