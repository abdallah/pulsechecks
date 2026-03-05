import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import CheckDetailPage from '../pages/CheckDetailPage'
import { api } from '../lib/api'

// Mock the API
vi.mock('../lib/api', () => ({
  api: {
    getCheck: vi.fn(),
    listPings: vi.fn(),
    listAlertChannels: vi.fn(),
  }
}))

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ teamId: 'team-123', checkId: 'check-123' }),
    useNavigate: () => vi.fn(),
  }
})

const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  name: 'Test User'
}

const mockCheck = {
  checkId: 'check-123',
  teamId: 'team-123',
  name: 'Test Check',
  status: 'up',
  periodSeconds: 3600,
  graceSeconds: 600,
  token: 'test-token-123',
  lastPingAt: '2024-12-24T10:00:00Z',
  createdAt: '2024-12-24T08:00:00Z',
  alertTopics: []
}

const mockRecentPings = [
  {
    checkId: 'check-123',
    timestamp: '1735027200000',
    receivedAt: '2024-12-24T10:00:00Z',
    pingType: 'success',
    data: 'Recent ping 1'
  },
  {
    checkId: 'check-123',
    timestamp: '1735023600000',
    receivedAt: '2024-12-24T09:00:00Z',
    pingType: 'success',
    data: 'Recent ping 2'
  }
]

const mockLatestPings = [
  {
    checkId: 'check-123',
    timestamp: '1735027200000',
    receivedAt: '2024-12-24T10:00:00Z',
    pingType: 'success',
    data: 'Latest ping'
  }
]

describe('CheckDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getCheck.mockResolvedValue(mockCheck)
    api.listAlertChannels.mockResolvedValue([])
  })

  const renderCheckDetailPage = () => {
    return render(
      <MemoryRouter initialEntries={['/teams/team-123/checks/check-123']}>
        <CheckDetailPage user={mockUser} onLogout={vi.fn()} />
      </MemoryRouter>
    )
  }

  test('renders check details and recent pings section', async () => {
    // Mock API calls - only need latest 20 pings now
    api.listPings.mockResolvedValueOnce(mockLatestPings)

    renderCheckDetailPage()

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Check that check details are displayed
    expect(screen.getByText('Test Check')).toBeInTheDocument()
    expect(screen.getByText('UP')).toBeInTheDocument()

    // Check that recent pings section is displayed
    expect(screen.getByText('Recent Pings (Latest 20)')).toBeInTheDocument()

    // Verify API calls were made correctly - only one call now
    expect(api.listPings).toHaveBeenCalledTimes(1)
    expect(api.listPings).toHaveBeenCalledWith('team-123', 'check-123', 20)
  })

  test('displays ping data in recent section', async () => {
    api.listPings.mockResolvedValueOnce(mockLatestPings)

    renderCheckDetailPage()

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Check that ping data is displayed in recent section
    expect(screen.getByText('Latest ping')).toBeInTheDocument()
  })

  test('handles empty ping history gracefully', async () => {
    api.listPings.mockResolvedValueOnce([])  // No pings

    renderCheckDetailPage()

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Check empty state message
    expect(screen.getByText('No pings recorded yet')).toBeInTheDocument()
  })
})
