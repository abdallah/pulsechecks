import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import CheckDetailPage from '../pages/CheckDetailPage'
import { api } from '../lib/api'
import { renderWithToast } from './test-utils'

// Mock the API
vi.mock('../lib/api', () => ({
  api: {
    getCheck: vi.fn(),
    getCheckStats: vi.fn(),
    getCheckErrorSummary: vi.fn(),
    getCheckUptime: vi.fn(),
    getTeam: vi.fn().mockResolvedValue({ teamId: 'team-123', name: 'Test Team', slug: 'test-team' }),
    listPings: vi.fn(),
    listMaintenanceWindows: vi.fn(),
    createMaintenanceWindow: vi.fn(),
    deleteMaintenanceWindow: vi.fn(),
    listAlertChannels: vi.fn(),
    listTeams: vi.fn(),
    updateCheck: vi.fn(),
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
    api.getCheckStats.mockResolvedValue({
      period: '24h',
      uptimePct: 99.5,
      totalPings: 20,
      successCount: 19,
      failCount: 1,
      avgResponseMs: 145,
      p95ResponseMs: 280,
      maxResponseMs: 300,
      minResponseMs: 100,
      latestResponseMs: 125,
      responseTimeSeries: [
        { timestamp: '2024-12-24T10:00:00Z', responseTimeMs: 125, pingType: 'success' },
        { timestamp: '2024-12-24T09:30:00Z', responseTimeMs: 280, pingType: 'fail' },
      ],
    })
    api.getCheckErrorSummary.mockResolvedValue({
      period: '24h',
      totalFailures: 2,
      mostCommonCode: '503',
      lastFailureAt: '2024-12-24T09:30:00Z',
      longestIncident: {
        startedAt: '2024-12-24T09:25:00Z',
        endedAt: '2024-12-24T09:30:00Z',
        durationSeconds: 300,
        failureCount: 2,
        dominantCode: '503',
      },
      failureCodes: [
        { code: '503', count: 2 },
      ],
      recentFailures: [
        {
          checkId: 'check-123',
          timestamp: '1735032600000',
          receivedAt: '2024-12-24T09:30:00Z',
          pingType: 'fail',
          code: '503',
          data: 'Service unavailable',
          responseTimeMs: 280,
        },
      ],
    })
    api.getCheckUptime.mockResolvedValue({
      from: '2024-12-23T10:00:00Z',
      to: '2024-12-24T10:00:00Z',
      excludeMaintenance: true,
      uptimePct: 97.2,
      totalObservedMinutes: 1440,
      downtimeMinutes: 40,
      excludedMaintenanceMinutes: 20,
      incidents: [
        {
          startedAt: '2024-12-24T09:00:00Z',
          endedAt: '2024-12-24T09:20:00Z',
          durationSeconds: 1200,
          failureCount: 2,
          dominantCode: '503',
        },
      ],
      maintenanceWindows: [],
    })
    api.listMaintenanceWindows.mockResolvedValue([])
    api.listAlertChannels.mockResolvedValue([])
    api.listTeams.mockResolvedValue([])
  })

  const renderCheckDetailPage = () => {
    return renderWithToast(
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

  test('shows Edit button and modal for HTTP checks', async () => {
    const httpCheck = {
      ...mockCheck,
      type: 'http',
      url: 'https://example.com/health',
      expectedStatusCode: 200,
      expectedString: null,
      failureThreshold: 1,
    }
    api.getCheck.mockResolvedValue(httpCheck)
    api.listPings.mockResolvedValueOnce([])
    api.updateCheck.mockResolvedValue({ ...httpCheck, url: 'https://example.com/new', expectedStatusCode: 201 })

    renderCheckDetailPage()

    await waitFor(() => {
      expect(screen.getByText('Monitored URL')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(api.getCheckStats).toHaveBeenCalledWith('team-123', 'check-123', '24h')
      expect(api.getCheckErrorSummary).toHaveBeenCalledWith('team-123', 'check-123', '24h')
      expect(api.getCheckUptime).toHaveBeenCalled()
      expect(api.listMaintenanceWindows).toHaveBeenCalledWith('team-123', 'check-123')
      expect(screen.getByText('Performance History')).toBeInTheDocument()
      expect(screen.getByText('Error Analysis')).toBeInTheDocument()
      expect(screen.getByText('Uptime Report')).toBeInTheDocument()
      expect(screen.getByText('97.2%')).toBeInTheDocument()
      expect(screen.getByText('40 min')).toBeInTheDocument()
      expect(screen.getByText((_, element) => element?.textContent === '145 ms')).toBeInTheDocument()
      expect(screen.getByText('99.5%')).toBeInTheDocument()
      expect(screen.getAllByText('503').length).toBeGreaterThan(0)
      expect(screen.getByText('Service unavailable')).toBeInTheDocument()
    })

    // Edit button should be visible (HTTP check edit specifically)
    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    const httpEditBtn = editButtons.find(btn => btn.textContent.includes('Edit') && btn.querySelector('svg'))
    expect(httpEditBtn).toBeInTheDocument()

    // Open modal
    fireEvent.click(httpEditBtn)
    expect(screen.getByText('Edit HTTP Check')).toBeInTheDocument()
    expect(screen.getByLabelText('URL')).toBeInTheDocument()
    expect(screen.getByLabelText('Expected Status Code')).toBeInTheDocument()

    // Submit form
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://example.com/new' } })
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(api.updateCheck).toHaveBeenCalledWith('team-123', 'check-123', expect.objectContaining({
        url: 'https://example.com/new',
      }))
    })
  })

  test('creates a team-wide maintenance window from the uptime form', async () => {
    const httpCheck = {
      ...mockCheck,
      type: 'http',
      url: 'https://example.com/health',
      expectedStatusCode: 200,
      expectedString: null,
      failureThreshold: 1,
    }
    api.getCheck.mockResolvedValue(httpCheck)
    api.listPings.mockResolvedValueOnce([])
    api.createMaintenanceWindow.mockResolvedValue({ ok: true })

    renderCheckDetailPage()

    await waitFor(() => {
      expect(screen.getByText('Uptime Report')).toBeInTheDocument()
    })

    const addMaintenanceButton = await screen.findByRole('button', { name: 'Add maintenance window' })
    const maintenanceForm = addMaintenanceButton.closest('form')
    const scopeSelect = maintenanceForm.querySelector('select')

    fireEvent.change(scopeSelect, { target: { value: 'team' } })
    fireEvent.click(addMaintenanceButton)

    await waitFor(() => {
      expect(api.createMaintenanceWindow).toHaveBeenCalledWith('team-123', expect.objectContaining({
        checkId: undefined,
      }))
    })
  })
})
