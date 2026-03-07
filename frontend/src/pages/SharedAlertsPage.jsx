import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Bell, Users, MessageSquare, Send, Plus, Settings, Trash2, Webhook } from 'lucide-react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

export default function SharedAlertsPage({ user, onLogout }) {
  const navigate = useNavigate()
  const [teams, setTeams] = useState([])
  const [sharedChannels, setSharedChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAddChannel, setShowAddChannel] = useState(false)
  const [editingChannel, setEditingChannel] = useState(null)
  const [newChannel, setNewChannel] = useState({
    name: '',
    displayName: '',
    type: 'mattermost',
    configuration: {},
    shared: true
  })

  useEffect(() => {
    loadSharedChannels()
  }, [])

  async function loadSharedChannels() {
    try {
      const teamsData = await api.listTeams()
      const teams = Array.isArray(teamsData) ? teamsData : teamsData.teams || []
      setTeams(teams)

      const allSharedChannels = []
      const seenChannels = new Set()

      for (const team of teams) {
        try {
          const channels = await api.listAlertChannels(team.teamId)
          const sharedChannels = channels.filter(channel => channel.shared)
          
          for (const channel of sharedChannels) {
            const channelKey = `${channel.teamId}-${channel.channelId}`
            if (!seenChannels.has(channelKey)) {
              seenChannels.add(channelKey)
              allSharedChannels.push({
                ...channel,
                teamName: team.name
              })
            }
          }
        } catch (error) {
          console.error(`Failed to load channels for team ${team.name}:`, error)
        }
      }

      setSharedChannels(allSharedChannels)
    } catch (error) {
      console.error('Failed to load shared channels:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateChannel(e) {
    e.preventDefault()
    if (!newChannel.name.trim() || !newChannel.displayName.trim()) return

    // Find user's first team to create the channel in
    const userTeam = teams[0]
    if (!userTeam) {
      alert('No team available to create channel')
      return
    }

    try {
      await api.createAlertChannel(userTeam.teamId, newChannel)
      setNewChannel({
        name: '',
        displayName: '',
        type: 'mattermost',
        configuration: {},
        shared: true
      })
      setShowAddChannel(false)
      loadSharedChannels()
    } catch (error) {
      alert('Failed to create channel: ' + error.message)
    }
  }

  async function handleDeleteChannel(channel) {
    if (!confirm(`Are you sure you want to delete "${channel.displayName}"?`)) return

    try {
      await api.deleteAlertChannel(channel.teamId, channel.channelId)
      loadSharedChannels()
    } catch (error) {
      alert('Failed to delete channel: ' + error.message)
    }
  }

  async function handleUpdateChannel(e) {
    e.preventDefault()
    
    try {
      const updateData = {
        displayName: editingChannel.displayName,
        configuration: editingChannel.configuration,
        shared: editingChannel.shared
      }
      
      await api.updateAlertChannel(editingChannel.teamId, editingChannel.channelId, updateData)
      setEditingChannel(null)
      loadSharedChannels()
    } catch (error) {
      alert('Failed to update channel: ' + error.message)
    }
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
        <div className="mb-8">
          <div className="flex items-center mb-4">
            <button
              onClick={() => navigate('/')}
              className="mr-4 p-2 text-gray-400 hover:text-gray-600"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Shared Alert Channels</h1>
              <p className="mt-1 text-sm text-gray-500">
                Shared alert channels available across all teams
              </p>
            </div>
          </div>
          
          <button
            onClick={() => setShowAddChannel(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Shared Channel
          </button>
        </div>

        {/* Create Channel Form */}
        {showAddChannel && (
          <div className="bg-white shadow sm:rounded-lg mb-6">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create Shared Alert Channel</h3>
              <form onSubmit={handleCreateChannel} className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Channel Name</label>
                    <input
                      type="text"
                      value={newChannel.name}
                      onChange={(e) => setNewChannel(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="critical-alerts"
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
                      placeholder="Critical Alerts"
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

                {newChannel.type === 'mattermost' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
                    <input
                      type="url"
                      value={newChannel.configuration.webhook_url || ''}
                      onChange={(e) => setNewChannel(prev => ({
                        ...prev,
                        configuration: { webhook_url: e.target.value }
                      }))}
                      placeholder="https://chat.example.com/hooks/shared-alerts"
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      required
                    />
                  </div>
                )}

                {newChannel.type === 'webhook' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
                    <input
                      type="url"
                      value={newChannel.configuration.webhook_url || ''}
                      onChange={(e) => setNewChannel(prev => ({
                        ...prev,
                        configuration: { webhook_url: e.target.value }
                      }))}
                      placeholder="https://hooks.example.com/shared-alerts"
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      required
                    />
                  </div>
                )}

                <div className="flex space-x-3">
                  <button
                    type="submit"
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
                  >
                    Create Shared Channel
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAddChannel(false)}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {sharedChannels.length === 0 ? (
          <div className="text-center py-12 bg-white shadow sm:rounded-lg">
            <Bell className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No shared alert channels</h3>
            <p className="mt-1 text-sm text-gray-500">
              Create shared alert channels in team settings to see them here.
            </p>
          </div>
        ) : (
          <div className="bg-white shadow overflow-hidden sm:rounded-md">
            <ul className="divide-y divide-gray-200">
              {sharedChannels.map((channel) => (
                <li key={`${channel.teamId}-${channel.channelId}`}>
                  <div className="px-4 py-4 flex items-center justify-between hover:bg-gray-50">
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
                        </div>
                        <div className="text-sm text-gray-500">
                          <Users className="inline h-4 w-4 mr-1" />
                          {channel.teamName} • {channel.type.toUpperCase()} • {channel.name}
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
                        onClick={() => handleDeleteChannel(channel)}
                        className="text-red-600 hover:text-red-800"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Edit Channel Modal */}
        {editingChannel && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
            <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
              <div className="mt-3">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Edit Shared Alert Channel</h3>
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

                  {(editingChannel.type === 'mattermost' || editingChannel.type === 'webhook') && (
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
                  )}

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
      </div>
    </Layout>
  )
}
