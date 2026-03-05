import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import DashboardPage from '../pages/DashboardPage';

// Mock the API
vi.mock('../lib/api', () => ({
  api: {
    listTeams: vi.fn(),
    createTeam: vi.fn(),
  }
}));

// Mock the auth
vi.mock('../lib/auth', () => ({
  getTokens: vi.fn(() => ({ accessToken: 'mock-token' }))
}));

import { api } from '../lib/api';

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

const mockUser = {
  userId: 'user-1',
  email: 'test@example.com',
  name: 'Test User'
};

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading state initially', () => {
    api.listTeams.mockImplementation(() => new Promise(() => {})); // Never resolves
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    expect(screen.getByText('Your Teams')).toBeInTheDocument();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  test('renders teams when loaded', async () => {
    const mockTeams = [
      {
        teamId: 'team-1',
        name: 'Test Team 1',
        role: 'admin',
        createdAt: '2023-01-01T00:00:00Z'
      },
      {
        teamId: 'team-2', 
        name: 'Test Team 2',
        role: 'member',
        createdAt: '2023-01-02T00:00:00Z'
      }
    ];

    api.listTeams.mockResolvedValue(mockTeams);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(screen.getByText('Test Team 1')).toBeInTheDocument();
      expect(screen.getByText('Test Team 2')).toBeInTheDocument();
    });

    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('member')).toBeInTheDocument();
  });

  test('renders empty state when no teams', async () => {
    api.listTeams.mockResolvedValue([]);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(screen.getByText('No teams')).toBeInTheDocument();
    });

    expect(screen.getByText('Get started by creating a new team.')).toBeInTheDocument();
  });

  test('renders page title', async () => {
    api.listTeams.mockResolvedValue([]);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(screen.getByText('Your Teams')).toBeInTheDocument();
    });
  });

  test('handles API error when loading teams', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.listTeams.mockRejectedValue(new Error('API Error'));
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to load teams:', expect.any(Error));
    });
    
    consoleSpy.mockRestore();
  });

  test('opens create team form when New Team button clicked', async () => {
    api.listTeams.mockResolvedValue([]);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(screen.getByText('New Team')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('New Team'));
    
    expect(screen.getByText('Create Team')).toBeInTheDocument();
    expect(screen.getByLabelText('Team Name')).toBeInTheDocument();
  });

  test('creates team successfully', async () => {
    api.listTeams.mockResolvedValue([]);
    api.createTeam.mockResolvedValue({ teamId: 'new-team', name: 'New Team' });
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      fireEvent.click(screen.getByText('New Team'));
    });

    fireEvent.change(screen.getByLabelText('Team Name'), {
      target: { value: 'My New Team' }
    });
    
    fireEvent.click(screen.getByText('Create Team'));
    
    await waitFor(() => {
      expect(api.createTeam).toHaveBeenCalledWith('My New Team');
    });
  });

  test('handles team creation error', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    api.listTeams.mockResolvedValue([]);
    api.createTeam.mockRejectedValue(new Error('Creation failed'));
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      fireEvent.click(screen.getByText('New Team'));
    });

    fireEvent.change(screen.getByLabelText('Team Name'), {
      target: { value: 'My New Team' }
    });
    
    fireEvent.click(screen.getByText('Create Team'));
    
    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to create team: Creation failed');
    });
    
    alertSpy.mockRestore();
  });

  test('cancels team creation', async () => {
    api.listTeams.mockResolvedValue([]);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      fireEvent.click(screen.getByText('New Team'));
    });

    fireEvent.click(screen.getByText('Cancel'));
    
    expect(screen.queryByText('Create Team')).not.toBeInTheDocument();
  });

  test('switches between grid and list view', async () => {
    const mockTeams = [
      { teamId: 'team-1', name: 'Test Team', role: 'admin', createdAt: '2023-01-01T00:00:00Z' }
    ];
    api.listTeams.mockResolvedValue(mockTeams);
    
    renderWithRouter(<DashboardPage user={mockUser} />);
    
    await waitFor(() => {
      expect(screen.getByText('Test Team')).toBeInTheDocument();
    });

    // Switch to list view
    const listViewButton = screen.getAllByRole('button').find(btn => 
      btn.querySelector('.lucide-list')
    );
    fireEvent.click(listViewButton);
    
    // Should still show the team
    expect(screen.getByText('Test Team')).toBeInTheDocument();
  });
});
