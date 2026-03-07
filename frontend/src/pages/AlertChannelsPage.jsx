import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Settings, Bell, MessageSquare, Send, Webhook } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

const CHANNEL_TYPES = {
  sns: { name: 'SNS Topic', icon: Bell, color: 'blue' },
  mattermost: { name: 'Mattermost', icon: MessageSquare, color: 'purple' },
  webhook: { name: 'Webhook', icon: Webhook, color: 'indigo' },
  telegram: { name: 'Telegram', icon: Send, color: 'sky' }
}

export default function AlertChannelsPage({ user, onLogout }) {
  const { teamId } = useParams()
  const navigate = useNavigate()
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateChannel, setShowCreateChannel] = useState(false)
  const [newChannel, setNewChannel] = useState({
    name: '',
    displayName: '',
    type: 'mattermost',
    configuration: {},
    shared: false
  })

  useEffect(() => {
    loadChannels()
  }, [teamId])

  async function loadChannels() {
    try {
      const data = await api.listAlertChannels(teamId)
      setChannels(data)
    } catch (error) {
      console.error('Failed to load alert channels:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateChannel(e) {
    e.preventDefault()
    if (!newChannel.name.trim() || !newChannel.displayName.trim()) return

    try {
      await api.createAlertChannel(teamId, newChannel)
      setNewChannel({
        name: '',
        displayName: '',
        type: 'mattermost',
        configuration: {},
        shared: false
      })
      setShowCreateChannel(false)
      loadChannels()
    } catch (error) {
      alert('Failed to create channel: ' + error.message)
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

  function handleConfigurationChange(key, value) {
    setNewChannel(prev => ({
      ...prev,
      configuration: {
        ...prev.configuration,
        [key]: value
      }
    }))
  }

  function renderConfigurationFields() {
    const { type } = newChannel

    if (type === 'sns') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">SNS Topic ARN</label>
          <input
            type="text"
            value={newChannel.configuration.topic_arn || ''}
            onChange={(e) => handleConfigurationChange('topic_arn', e.target.value)}
            placeholder="arn:aws:sns:us-east-1:123456789012:my-topic"
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (type === 'mattermost') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
          <input
            type="url"
            value={newChannel.configuration.webhook_url || ''}
            onChange={(e) => handleConfigurationChange('webhook_url', e.target.value)}
            placeholder="https://chat.example.com/hooks/your-webhook-id"
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (type === 'webhook') {
      return (
        <div>
          <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
          <input
            type="url"
            value={newChannel.configuration.webhook_url || ''}
            onChange={(e) => handleConfigurationChange('webhook_url', e.target.value)}
            placeholder="https://hooks.example.com/alerts"
            className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            required
          />
        </div>
      )
    }

    if (type === 'telegram') {
      return (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Bot Token</label>
            <input
              type="text"
              value={newChannel.configuration.bot_token || ''}
              onChange={(e) => handleConfigurationChange('bot_token', e.target.value)}
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Chat ID</label>
            <input
              type="text"
              value={newChannel.configuration.chat_id || ''}
              onChange={(e) => handleConfigurationChange('chat_id', e.target.value)}
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

  if (loading) {
    return (
      <Layout user={user} onLogout={onLogout}>
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout user={user} onLogout={onLogout}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center mb-4">
            <button
              onClick={() => navigate(`/teams/${teamId}/settings`)}
              className="mr-4 p-2 text-gray-400 hover:text-gray-600"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Alert Channels</h1>
              <p className="mt-1 text-sm text-gray-500">
                Configure notification channels for alerts (SNS, Mattermost, Telegram)
              </p>
            </div>
          </div>
          
          <button
            onClick={() => setShowCreateChannel(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Channel
          </button>
        </div>

        {/* Create Channel Form */}
        {showCreateChannel && (
          <div className="bg-white shadow sm:rounded-lg mb-6">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create Alert Channel</h3>
              <form onSubmit={handleCreateChannel} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Channel Name</label>
                    <input
                      type="text"
                      value={newChannel.name}
                      onChange={(e) => setNewChannel(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="my-alerts"
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Display Name</label>
                    <input
                      type="text"
                      value={newChannel.displayName}
                      onChange={(e) => setNewChannel(prev => ({ ...prev, displayName: e.target.value }))}
                      placeholder="My Alerts Channel"
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Channel Type</label>
                  <select
                    value={newChannel.type}
                    onChange={(e) => setNewChannel(prev => ({ ...prev, type: e.target.value, configuration: {} }))}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  >
                    <option value="sns">SNS Topic</option>
                    <option value="mattermost">Mattermost</option>
                    <option value="webhook">Webhook</option>
                    <option value="telegram">Telegram</option>
                  </select>
                </div>

                {renderConfigurationFields()}

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    checked={newChannel.shared}
                    onChange={(e) => setNewChannel(prev => ({ ...prev, shared: e.target.checked }))}
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
                    onClick={() => setShowCreateChannel(false)}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Channels List */}
        {channels.length === 0 ? (
          <div className="text-center py-12 bg-white shadow sm:rounded-lg">
            <Bell className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No alert channels</h3>
            <p className="mt-1 text-sm text-gray-500">
              Get started by creating your first alert channel.
            </p>
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {channels.map((channel) => {
                const typeInfo = CHANNEL_TYPES[channel.type] || CHANNEL_TYPES.sns
                const Icon = typeInfo.icon
                
                return (
                  <li key={channel.channelId}>
                    <div className="px-4 py-4 flex items-center justify-between hover:bg-gray-50">
                      <div className="flex items-center">
                        <div className={`flex-shrink-0 h-10 w-10 rounded-full bg-${typeInfo.color}-100 flex items-center justify-center`}>
                          <Icon className={`h-5 w-5 text-${typeInfo.color}-600`} />
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900">
                            {channel.displayName}
                          </div>
                          <div className="text-sm text-gray-500">
                            {typeInfo.name} • {channel.name}
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
                          onClick={() => navigate(`/teams/${teamId}/channels/${channel.channelId}`)}
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
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
                )
              })}
            </ul>
          </div>
        )}
      </div>
    </Layout>
  )
}
