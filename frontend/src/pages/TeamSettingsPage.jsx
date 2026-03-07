import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Users, Plus, Trash2, Shield, Bell, Webhook, Settings, X, MessageSquare, Send } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

export default function TeamSettingsPage({ user, onLogout }) {
  const { teamId } = useParams()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('members')
  const [team, setTeam] = useState(null)
  const [members, setMembers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAddMember, setShowAddMember] = useState(false)
  const [showAddAlert, setShowAddAlert] = useState(false)
  const [showTopicDetails, setShowTopicDetails] = useState(false)
  const [selectedTopic, setSelectedTopic] = useState(null)
  const [topicDetails, setTopicDetails] = useState(null)
  const [newMemberEmail, setNewMemberEmail] = useState('')
  const [newMemberRole, setNewMemberRole] = useState('member')
  const [newAlertName, setNewAlertName] = useState('')
  const [newAlertDisplayName, setNewAlertDisplayName] = useState('')
  const [newAlertShared, setNewAlertShared] = useState(false)
  const [newChannelType, setNewChannelType] = useState('mattermost')
  const [newChannelConfig, setNewChannelConfig] = useState({})
  const [channels, setChannels] = useState([])
  const [editingChannel, setEditingChannel] = useState(null)
  const [newSubscriptionProtocol, setNewSubscriptionProtocol] = useState('email')
  const [newSubscriptionEndpoint, setNewSubscriptionEndpoint] = useState('')
  const [mattermostWebhook, setMattermostWebhook] = useState('')
  const [mattermostLoading, setMattermostLoading] = useState(false)
  const [mattermostWebhooks, setMattermostWebhooks] = useState([])
  const [newWebhookUrl, setNewWebhookUrl] = useState('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)

  useEffect(() => {
    loadTeam()
    if (activeTab === 'members') {
      loadMembers()
    } else if (activeTab === 'alerts') {
      loadAlerts()
      loadChannels()
    }
  }, [teamId, activeTab])

  async function loadTeam() {
    try {
      const teamData = await api.getTeam(teamId)
      setTeam(teamData)
    } catch (error) {
      console.error('Failed to load team:', error)
    }
  }

  async function loadMembers() {
    try {
      const data = await api.listTeamMembers(teamId)
      setMembers(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Failed to load members:', error)
    } finally {
      setLoading(false)
    }
  }

  async function loadAlerts() {
    try {
      const data = await api.listAlertChannels(teamId)
      console.log('Alerts data:', data) // Debug log
      setAlerts(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Failed to load alerts:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAddMember(e) {
    e.preventDefault()
    if (!newMemberEmail.trim()) return

    try {
      await api.addTeamMember(teamId, newMemberEmail.trim(), newMemberRole)
      setNewMemberEmail('')
      setNewMemberRole('member')
      setShowAddMember(false)
      loadMembers()
    } catch (error) {
      alert('Failed to add member: ' + error.message)
    }
  }

  async function handleRemoveMember(userId) {
    if (!confirm('Are you sure you want to remove this member?')) return

    try {
      await api.removeTeamMember(teamId, userId)
      loadMembers()
    } catch (error) {
      alert('Failed to remove member: ' + error.message)
    }
  }

  async function handleDeleteInvitation(email) {
    if (!confirm('Are you sure you want to delete this invitation?')) return

    try {
      await api.deleteTeamInvitation(teamId, email)
      loadMembers()
    } catch (error) {
      alert('Failed to delete invitation: ' + error.message)
    }
  }

  async function loadMattermostWebhook() {
    try {
      const data = await api.getTeamMattermostWebhook(teamId)
      setMattermostWebhook(data.webhook_url || '')
    } catch (error) {
      console.error('Failed to load Mattermost webhook:', error)
    }
  }

  async function handleMattermostWebhookSave() {
    setMattermostLoading(true)
    try {
      await api.updateTeamMattermostWebhook(teamId, mattermostWebhook)
      alert('Mattermost webhook updated successfully!')
    } catch (error) {
      alert('Failed to update Mattermost webhook: ' + error.message)
    } finally {
      setMattermostLoading(false)
    }
  }

  async function loadMattermostWebhooks() {
    try {
      const data = await api.getTeamMattermostWebhooks(teamId)
      setMattermostWebhooks(data.webhooks || [])
    } catch (error) {
      console.error('Failed to load Mattermost webhooks:', error)
    }
  }

  async function handleAddWebhook() {
    if (!newWebhookUrl.trim()) return
    
    try {
      await api.addTeamMattermostWebhook(teamId, newWebhookUrl.trim())
      setNewWebhookUrl('')
      loadMattermostWebhooks()
    } catch (error) {
      alert('Failed to add webhook: ' + error.message)
    }
  }

  async function handleRemoveWebhook(webhookUrl) {
    if (!confirm('Are you sure you want to remove this webhook?')) return
    
    try {
      await api.removeTeamMattermostWebhook(teamId, webhookUrl)
      loadMattermostWebhooks()
    } catch (error) {
      alert('Failed to remove webhook: ' + error.message)
    }
  }

  async function handleRoleChange(userId, newRole) {
    try {
      await api.updateTeamMemberRole(teamId, userId, newRole)
      loadMembers()
    } catch (error) {
      alert('Failed to update role: ' + error.message)
    }
  }

  async function handleAddAlert(e) {
    e.preventDefault()
    if (!newAlertName.trim() || !newAlertDisplayName.trim()) return

    try {
      const channelData = {
        name: newAlertName.trim(),
        displayName: newAlertDisplayName.trim(),
        type: newChannelType,
        configuration: newChannelConfig,
        shared: newAlertShared
      }
      
      await api.createAlertChannel(teamId, channelData)
      setNewAlertName('')
      setNewAlertDisplayName('')
      setNewChannelType('mattermost')
      setNewChannelConfig({})
      setNewAlertShared(false)
      setShowAddAlert(false)
      loadChannels()
    } catch (error) {
      alert('Failed to create channel: ' + error.message)
    }
  }

  async function loadChannels() {
    try {
      const data = await api.listAlertChannels(teamId)
      console.log('Alert channels loaded:', data)
      setChannels(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error('Failed to load alert channels:', error)
    }
  }

  async function handleDeleteChannel(channelId) {
    if (!confirm('Are you sure you want to delete this alert channel?')) return

    try {
      await api.deleteAlertChannel(teamId, channelId)
      loadChannels()
    } catch (error) {
      alert('Failed to delete channel: ' + error.message)
    }
  }

  function renderChannelConfiguration() {
    if (newChannelType === 'sns') {
      return (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
          <p className="text-sm text-blue-700">
            SNS topic will be created automatically when you create this channel.
          </p>
        </div>
      )
    }

    if (newChannelType === 'mattermost') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
          <input
            type="url"
            value={newChannelConfig.webhook_url || ''}
            onChange={(e) => setNewChannelConfig({ webhook_url: e.target.value })}
            placeholder="https://chat.example.com/hooks/your-webhook-id"
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (newChannelType === 'webhook') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
          <input
            type="url"
            value={newChannelConfig.webhook_url || ''}
            onChange={(e) => setNewChannelConfig({ webhook_url: e.target.value })}
            placeholder="https://hooks.example.com/alerts"
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (newChannelType === 'telegram') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Bot Token</label>
            <input
              type="text"
              value={newChannelConfig.bot_token || ''}
              onChange={(e) => setNewChannelConfig({ ...newChannelConfig, bot_token: e.target.value })}
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Chat ID</label>
            <input
              type="text"
              value={newChannelConfig.chat_id || ''}
              onChange={(e) => setNewChannelConfig({ ...newChannelConfig, chat_id: e.target.value })}
              placeholder="-1001234567890"
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              required
            />
          </div>
        </div>
      )
    }

    return null
  }

  async function handleUpdateChannel(e) {
    e.preventDefault()
    
    try {
      const updateData = {
        displayName: editingChannel.displayName,
        configuration: editingChannel.configuration,
        shared: editingChannel.shared
      }
      
      await api.updateAlertChannel(teamId, editingChannel.channelId, updateData)
      setEditingChannel(null)
      loadChannels()
    } catch (error) {
      alert('Failed to update channel: ' + error.message)
    }
  }

  function renderEditChannelConfiguration() {
    if (!editingChannel) return null

    if (editingChannel.type === 'sns') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">SNS Topic ARN</label>
          <input
            type="text"
            value={editingChannel.configuration?.topic_arn || ''}
            onChange={(e) => setEditingChannel({
              ...editingChannel,
              configuration: { ...editingChannel.configuration, topic_arn: e.target.value }
            })}
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (editingChannel.type === 'mattermost' || editingChannel.type === 'webhook') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
          <input
            type="url"
            value={editingChannel.configuration?.webhook_url || ''}
            onChange={(e) => setEditingChannel({
              ...editingChannel,
              configuration: { ...editingChannel.configuration, webhook_url: e.target.value }
            })}
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (editingChannel.type === 'telegram') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Bot Token</label>
            <input
              type="text"
              value={editingChannel.configuration?.bot_token || ''}
              onChange={(e) => setEditingChannel({
                ...editingChannel,
                configuration: { ...editingChannel.configuration, bot_token: e.target.value }
              })}
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Chat ID</label>
            <input
              type="text"
              value={editingChannel.configuration?.chat_id || ''}
              onChange={(e) => setEditingChannel({
                ...editingChannel,
                configuration: { ...editingChannel.configuration, chat_id: e.target.value }
              })}
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              required
            />
          </div>
        </div>
      )
    }

    return null
  }

  async function handleDeleteAlert(topicArn) {
    // Legacy alert topics are no longer supported
    alert('Alert topics have been replaced with alert channels. Please use the Channels page to manage notifications.')
  }

  async function handleShowTopicDetails(topic) {
    setSelectedTopic(topic)
    setShowTopicDetails(true)
    try {
      const topicArn = topic.topicArn || topic.topic_arn
      if (!topicArn) {
        console.error('No topic ARN found:', topic)
        alert('Error: Topic ARN not found')
        return
      }
      const details = await api.getAlertTopicDetails(teamId, topicArn)
      setTopicDetails(details)
    } catch (error) {
      console.error('Failed to load topic details:', error)
      setTopicDetails(null)
    }
  }

  async function handleSubscribe(e) {
    e.preventDefault()
    if (!selectedTopic || !newSubscriptionEndpoint.trim()) return

    try {
      const topicArn = selectedTopic.topicArn || selectedTopic.topic_arn
      // Legacy subscription functionality no longer supported
      alert('Alert topic subscriptions have been replaced with alert channels. Please use the Channels page to manage notifications.')
      setNewSubscriptionEndpoint('')
      alert('Subscription created! Check your email/endpoint for confirmation.')
      // Reload topic details
      handleShowTopicDetails(selectedTopic)
    } catch (error) {
      alert('Failed to subscribe: ' + error.message)
    }
  }

  async function handleUnsubscribe(subscriptionArn) {
    if (!confirm('Are you sure you want to unsubscribe?')) return

    try {
      const topicArn = selectedTopic.topicArn || selectedTopic.topic_arn
      await api.unsubscribeFromAlertTopic(teamId, topicArn, subscriptionArn)
      alert('Unsubscribed successfully!')
      // Reload topic details
      handleShowTopicDetails(selectedTopic)
    } catch (error) {
      alert('Failed to unsubscribe: ' + error.message)
    }
  }

  async function handleDeleteTeam() {
    if (deleteConfirmText !== team?.name) {
      alert('Please type the team name exactly to confirm deletion')
      return
    }

    setDeleteLoading(true)
    try {
      await api.deleteTeam(teamId, team.name)
      alert(`Team "${team.name}" has been permanently deleted`)
      navigate('/')
    } catch (error) {
      alert('Failed to delete team: ' + error.message)
    } finally {
      setDeleteLoading(false)
    }
  }

  if (loading) {
    return (
      <Layout user={user} onLogout={onLogout}>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="space-y-6">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Teams
          </button>
          {team ? (
            <h1 className="text-3xl font-bold text-gray-900">
              Team{' '}
              <button
                onClick={() => navigate(`/teams/${teamId}/checks`)}
                className="text-blue-600 hover:text-blue-800 underline"
              >
                {team.name}
              </button>{' '}
              Settings
            </h1>
          ) : (
            <h1 className="text-3xl font-bold text-gray-900">Team Settings</h1>
          )}
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('members')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'members'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Users className="h-4 w-4 inline mr-2" />
              Members
            </button>
            <button
              onClick={() => setActiveTab('alerts')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'alerts'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Bell className="h-4 w-4 inline mr-2" />
              Alert Channels
            </button>
            <button
              onClick={() => setActiveTab('danger')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'danger'
                  ? 'border-red-500 text-red-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Trash2 className="h-4 w-4 inline mr-2" />
              Danger Zone
            </button>
          </nav>
        </div>

        {/* Members Tab */}
        {activeTab === 'members' && (
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Team Members ({members.length})
              </h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Manage who has access to this team
              </p>
            </div>
            <button
              onClick={() => setShowAddMember(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Member
            </button>
          </div>

          {showAddMember && (
            <div className="border-t border-gray-200 px-4 py-4 bg-gray-50">
              <form onSubmit={handleAddMember} className="flex items-end space-x-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700">Email</label>
                  <input
                    type="email"
                    value={newMemberEmail}
                    onChange={(e) => setNewMemberEmail(e.target.value)}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="user@example.com"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Role</label>
                  <select
                    value={newMemberRole}
                    onChange={(e) => setNewMemberRole(e.target.value)}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="flex space-x-2">
                  <button
                    type="submit"
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
                  >
                    Add
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddMember(false)
                      setNewMemberEmail('')
                      setNewMemberRole('member')
                    }}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          <div className="border-t border-gray-200">
            {members.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No members found
              </div>
            ) : (
              <ul className="divide-y divide-gray-200">
                {members.map((member) => (
                  <li key={member.userId} className="px-4 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                            <span className="text-sm font-medium text-gray-700">
                              {member.name?.charAt(0)?.toUpperCase() || '?'}
                            </span>
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">
                            {member.name}
                            {member.status === 'pending' && (
                              <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                Pending
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-gray-500">{member.email}</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <select
                          value={member.role}
                          onChange={(e) => handleRoleChange(member.userId, e.target.value)}
                          className="text-sm border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                          disabled={member.userId === user.sub || member.status === 'pending'}
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                        {member.role === 'admin' && member.status === 'active' && (
                          <Shield className="h-4 w-4 text-blue-500" />
                        )}
                        {member.userId !== user.sub && member.status === 'active' && (
                          <button
                            onClick={() => handleRemoveMember(member.userId)}
                            className="text-red-600 hover:text-red-500"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                        {member.status === 'pending' && (
                          <button
                            onClick={() => handleDeleteInvitation(member.email)}
                            className="text-red-600 hover:text-red-500"
                            title="Delete invitation"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        )}

        {/* Alerts Tab */}
        {activeTab === 'alerts' && (
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
              <div>
                <h3 className="text-lg leading-6 font-medium text-gray-900 flex items-center">
                  <Bell className="h-5 w-5 mr-2" />
                  Alert Channels
                </h3>
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  Configure notification channels for alerts (SNS, Mattermost, Webhook, Telegram).
                </p>
              </div>
              <button
                onClick={() => setShowAddAlert(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Channel
              </button>
            </div>

            {showAddAlert && (
              <div className="border-t border-gray-200 px-4 py-4 bg-gray-50">
                <form onSubmit={handleAddAlert} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Channel Name</label>
                      <input
                        type="text"
                        value={newAlertName}
                        onChange={(e) => setNewAlertName(e.target.value)}
                        placeholder="my-alerts"
                        className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Display Name</label>
                      <input
                        type="text"
                        value={newAlertDisplayName}
                        onChange={(e) => setNewAlertDisplayName(e.target.value)}
                        placeholder="My Alerts Channel"
                        className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        required
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Channel Type</label>
                    <select
                      value={newChannelType}
                      onChange={(e) => setNewChannelType(e.target.value)}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    >
                      <option value="sns">SNS Topic</option>
                      <option value="mattermost">Mattermost</option>
                      <option value="webhook">Webhook</option>
                      <option value="telegram">Telegram</option>
                    </select>
                  </div>

                  {renderChannelConfiguration()}

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={newAlertShared}
                      onChange={(e) => setNewAlertShared(e.target.checked)}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label className="ml-2 block text-sm text-gray-900">
                      Shared channel (can be used by other teams)
                    </label>
                  </div>

                  <div className="flex space-x-3">
                    <button
                      type="submit"
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
                    >
                      Create Channel
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowAddAlert(false)}
                      className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            <div className="border-t border-gray-200">
              {channels.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500">
                  No alert channels configured
                </div>
              ) : (
                <ul className="divide-y divide-gray-200">
                  {channels.map((channel) => (
                    <li key={channel.channelId} className="px-4 py-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="flex-shrink-0">
                            {channel.type === 'sns' && <Bell className="h-8 w-8 text-blue-500" />}
                            {channel.type === 'mattermost' && <MessageSquare className="h-8 w-8 text-purple-500" />}
                            {channel.type === 'webhook' && <Webhook className="h-8 w-8 text-indigo-500" />}
                            {channel.type === 'telegram' && <Send className="h-8 w-8 text-sky-500" />}
                          </div>
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">
                              {channel.displayName}
                              {channel.shared && (
                                <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  Shared
                                </span>
                              )}
                            </div>
                            <div className="text-sm text-gray-500">
                              {channel.type.toUpperCase()} • {channel.name}
                              {channel.shared && (
                                <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  Shared
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => setEditingChannel(channel)}
                            className="text-blue-600 hover:text-blue-800"
                          >
                            <Settings className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteChannel(channel.channelId)}
                            className="text-red-600 hover:text-red-800"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Edit Channel Modal */}
        {editingChannel && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
              <div className="mt-3">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Edit Alert Channel</h3>
                <form onSubmit={handleUpdateChannel} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Display Name</label>
                    <input
                      type="text"
                      value={editingChannel.displayName}
                      onChange={(e) => setEditingChannel({...editingChannel, displayName: e.target.value})}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      required
                    />
                  </div>

                  {renderEditChannelConfiguration()}

                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={editingChannel.shared}
                      onChange={(e) => setEditingChannel({...editingChannel, shared: e.target.checked})}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label className="ml-2 block text-sm text-gray-900">
                      Shared channel (can be used by other teams)
                    </label>
                  </div>

                  <div className="flex space-x-3">
                    <button
                      type="submit"
                      className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
                    >
                      Update Channel
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingChannel(null)}
                      className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Danger Zone Tab */}
        {activeTab === 'danger' && (
          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="px-4 py-5 sm:px-6">
              <h3 className="text-lg leading-6 font-medium text-red-900 flex items-center">
                <Trash2 className="h-5 w-5 mr-2" />
                Danger Zone
              </h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Irreversible and destructive actions.
              </p>
            </div>
            
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <Trash2 className="h-6 w-6 text-red-600" />
                  </div>
                  <div className="ml-3 flex-1">
                    <h4 className="text-lg font-medium text-red-900">Delete Team</h4>
                    <p className="mt-2 text-sm text-red-700">
                      Permanently delete this team and all associated data. This action cannot be undone.
                    </p>
                    <p className="mt-2 text-sm text-red-700 font-medium">
                      This will delete:
                    </p>
                    <ul className="mt-1 text-sm text-red-700 list-disc list-inside">
                      <li>All team members and invitations</li>
                      <li>All checks and their ping history</li>
                      <li>All alert channels and configurations</li>
                      <li>All Mattermost webhook integrations</li>
                    </ul>
                    
                    <div className="mt-4">
                      <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete Team
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
              <div className="mt-3">
                <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                  <Trash2 className="h-6 w-6 text-red-600" />
                </div>
                <h3 className="text-lg font-medium text-gray-900 mt-4 text-center">Delete Team</h3>
                <div className="mt-4">
                  <p className="text-sm text-gray-500 text-center mb-4">
                    This action cannot be undone. This will permanently delete the team "{team?.name}" and all associated data.
                  </p>
                  <p className="text-sm text-gray-700 font-medium mb-2">
                    Please type <span className="font-mono bg-gray-100 px-1 rounded">{team?.name}</span> to confirm:
                  </p>
                  <input
                    type="text"
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    className="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm"
                    placeholder={team?.name}
                  />
                </div>
                <div className="flex space-x-3 mt-6">
                  <button
                    onClick={handleDeleteTeam}
                    disabled={deleteLoading || deleteConfirmText !== team?.name}
                    className="flex-1 px-4 py-2 bg-red-600 text-white text-base font-medium rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleteLoading ? 'Deleting...' : 'Delete Team'}
                  </button>
                  <button
                    onClick={() => {
                      setShowDeleteConfirm(false)
                      setDeleteConfirmText('')
                    }}
                    disabled={deleteLoading}
                    className="flex-1 px-4 py-2 bg-white text-gray-500 text-base font-medium rounded-md shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
