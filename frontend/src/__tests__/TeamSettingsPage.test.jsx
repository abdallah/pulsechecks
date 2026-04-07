import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, test, expect, vi, beforeEach } from 'vitest'
import TeamSettingsPage from '../pages/TeamSettingsPage'
import { api } from '../lib/api'
import { renderWithToast } from './test-utils'

vi.mock('../lib/api', () => ({
  api: {
    getTeam: vi.fn(),
    listTeamMembers: vi.fn(),
    listAlertChannels: vi.fn(),
    listApiTokens: vi.fn(),
    listReports: vi.fn(),
    listChecks: vi.fn(),
    createReport: vi.fn(),
    downloadReport: vi.fn(),
    deleteReport: vi.fn(),
  }
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ teamId: 'team-123' }),
    useNavigate: () => vi.fn(),
  }
})

const user = {
  sub: 'user-123',
  email: 'test@example.com',
  name: 'Test User',
}

describe('TeamSettingsPage reports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getTeam.mockResolvedValue({ teamId: 'team-123', name: 'Test Team' })
    api.listTeamMembers.mockResolvedValue([])
    api.listAlertChannels.mockResolvedValue([])
    api.listApiTokens.mockResolvedValue([])
    api.listReports.mockResolvedValue([])
    api.listChecks.mockResolvedValue([{ checkId: 'check-123', name: 'API Health' }])
    api.createReport.mockResolvedValue({ reportId: 'report-123', reportType: 'summary', format: 'json' })
  })

  function renderPage() {
    return renderWithToast(
      <MemoryRouter initialEntries={['/teams/team-123/settings']}>
        <TeamSettingsPage user={user} onLogout={vi.fn()} />
      </MemoryRouter>
    )
  }

  test('generates a team-scoped report from the reports tab', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Team Settings')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /reports/i }))

    await waitFor(() => {
      expect(screen.getByText('Downloadable Reports')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Generate Report' }))

    await waitFor(() => {
      expect(api.createReport).toHaveBeenCalledWith('team-123', expect.objectContaining({
        reportType: 'summary',
        format: 'json',
        checkId: undefined,
      }))
    })
  })
})
