import { config } from '../config'
import { getIdToken, logout, clearTokens } from './auth'

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl
  }
  
  async request(path, options = {}) {
    const token = getIdToken()
    
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    })
    
    if (!response.ok) {
      // Auto-logout on 401 (expired/invalid token)
      if (response.status === 401) {
        // Clear tokens locally first to prevent redirect loop
        clearTokens()
        // Redirect to login instead of Cognito logout to avoid loop
        window.location.href = '/login'
        return
      }
      
      const error = await response.json().catch(() => ({ error: 'Request failed' }))
      throw new Error(error.error || `HTTP ${response.status}`)
    }
    
    return response.json()
  }
  
  // User
  async getMe() {
    return this.request('/me')
  }
  
  // Teams
  async createTeam(name) {
    return this.request('/teams', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  }
  
  async listTeams() {
    return this.request('/teams')
  }
  
  async getTeam(teamId) {
    return this.request(`/teams/${teamId}`)
  }

  async updateTeam(teamId, teamData) {
    return this.request(`/teams/${teamId}`, {
      method: 'PATCH',
      body: JSON.stringify(teamData),
    })
  }

  async deleteTeam(teamId, teamName) {
    return this.request(`/teams/${teamId}`, {
      method: 'DELETE',
      body: JSON.stringify({ team_name: teamName }),
    })
  }
  
  // Checks
  async listChecks(team_id) {
    return this.request(`/teams/${team_id}/checks`)
  }
  
  async createCheck(team_id, data) {
    return this.request(`/teams/${team_id}/checks`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }
  
  async getCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}`)
  }
  
  async updateCheck(team_id, check_id, data) {
    return this.request(`/teams/${team_id}/checks/${check_id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }
  
  async pauseCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}/pause`, {
      method: 'POST',
    })
  }
  
  async resumeCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}/resume`, {
      method: 'POST',
    })
  }
  
  async rotateCheckToken(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}/rotate-token`, {
      method: 'POST',
    })
  }
  
  async deleteCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}`, {
      method: 'DELETE',
    })
  }

  async bulkPauseChecks(team_id, checkIds) {
    return this.request(`/teams/${team_id}/checks/bulk/pause`, {
      method: 'POST',
      body: JSON.stringify({ check_ids: checkIds }),
    })
  }

  async bulkResumeChecks(team_id, checkIds) {
    return this.request(`/teams/${team_id}/checks/bulk/resume`, {
      method: 'POST',
      body: JSON.stringify({ check_ids: checkIds }),
    })
  }

  async escalateCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}/escalate`, {
      method: 'POST',
    })
  }

  async suppressCheck(team_id, check_id) {
    return this.request(`/teams/${team_id}/checks/${check_id}/suppress`, {
      method: 'POST',
    })
  }
  
  async listPings(team_id, check_id, limit = 50, since = null) {
    const params = new URLSearchParams({ limit: limit.toString() })
    if (since) {
      params.append('since', since.toString())
    }
    return this.request(`/teams/${team_id}/checks/${check_id}/pings?${params}`)
  }

  // Team member management
  async listTeamMembers(team_id) {
    return this.request(`/teams/${team_id}/members`)
  }

  async addTeamMember(teamId, email, role = 'member') {
    return this.request(`/teams/${teamId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    })
  }

  async removeTeamMember(teamId, userId) {
    return this.request(`/teams/${teamId}/members/${userId}`, {
      method: 'DELETE',
    })
  }

  async deleteTeamInvitation(teamId, email) {
    return this.request(`/teams/${teamId}/invitations/${encodeURIComponent(email)}`, {
      method: 'DELETE',
    })
  }

  // Alert Channels (new unified system)
  async listAlertChannels(teamId) {
    return this.request(`/teams/${teamId}/channels`)
  }

  async createAlertChannel(teamId, channelData) {
    return this.request(`/teams/${teamId}/channels`, {
      method: 'POST',
      body: JSON.stringify(channelData),
    })
  }

  async getAlertChannel(teamId, channelId) {
    return this.request(`/teams/${teamId}/channels/${channelId}`)
  }

  async updateAlertChannel(teamId, channelId, channelData) {
    return this.request(`/teams/${teamId}/channels/${channelId}`, {
      method: 'PATCH',
      body: JSON.stringify(channelData),
    })
  }

  async deleteAlertChannel(teamId, channelId) {
    return this.request(`/teams/${teamId}/channels/${channelId}`, {
      method: 'DELETE',
    })
  }

  async updateTeamMemberRole(teamId, userId, role) {
    return this.request(`/teams/${teamId}/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    })
  }
}

export const api = new ApiClient(config.apiUrl)
