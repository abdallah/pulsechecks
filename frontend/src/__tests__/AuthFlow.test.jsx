import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { isAuthenticated, setTokens, clearTokens, getAccessToken, login, handleCallback } from '../lib/auth';
import { api } from '../lib/api';
import LoginPage from '../pages/LoginPage';
import CallbackPage from '../pages/CallbackPage';
import DashboardPage from '../pages/DashboardPage';

// Mock the auth functions
vi.mock('../lib/auth', () => ({
  isAuthenticated: vi.fn(),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(() => 'mock-access-token'),
  login: vi.fn(),
  handleCallback: vi.fn()
}));

// Mock the API
vi.mock('../lib/api', () => ({
  api: {
    getMe: vi.fn(),
    listTeams: vi.fn(),
  }
}));

// Create a test version of App without BrowserRouter
function TestApp() {
  const [authenticated, setAuthenticated] = useState(isAuthenticated())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    if (authenticated) {
      loadUser()
    } else {
      setLoading(false)
    }
  }, [authenticated])
  
  async function loadUser() {
    try {
      const userData = await api.getMe()
      setUser(userData)
    } catch (error) {
      clearTokens()
      setAuthenticated(false)
    } finally {
      setLoading(false)
    }
  }
  
  function handleLogin(tokens) {
    setTokens(tokens)
    setAuthenticated(true)
  }
  
  function handleLogout() {
    clearTokens()
    setAuthenticated(false)
    setUser(null)
  }
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    )
  }
  
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/callback" element={<CallbackPage onLogin={handleLogin} />} />
      
      {authenticated ? (
        <>
          <Route path="/" element={<DashboardPage user={user} onLogout={handleLogout} />} />
        </>
      ) : (
        <Route path="*" element={<Navigate to="/login" replace />} />
      )}
    </Routes>
  )
}

const renderWithRouter = (initialEntries = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <TestApp />
    </MemoryRouter>
  );
};

describe('Auth Flow Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows login page when not authenticated', () => {
    isAuthenticated.mockReturnValue(false);
    
    renderWithRouter();
    
    expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    expect(screen.getByText('Serverless job monitoring made simple')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in with google workspace/i })).toBeInTheDocument();
  });

  test.skip('shows dashboard when authenticated', async () => {
    isAuthenticated.mockReturnValue(true);
    api.getMe.mockResolvedValue({
      userId: 'user-123',
      email: 'test@example.com',
      name: 'Test User'
    });
    api.listTeams.mockResolvedValue([]);
    
    renderWithRouter();
    
    await waitFor(() => {
      expect(screen.getByText('Your Teams')).toBeInTheDocument();
    });

    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('No teams')).toBeInTheDocument();
  });

  test('handles callback page', async () => {
    isAuthenticated.mockReturnValue(false);
    
    renderWithRouter(['/callback']);
    
    expect(screen.getByText('Completing sign in...')).toBeInTheDocument();
  });

  test('redirects to login when accessing protected route while unauthenticated', () => {
    isAuthenticated.mockReturnValue(false);
    
    renderWithRouter(['/teams/123/checks']);
    
    expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in with google workspace/i })).toBeInTheDocument();
  });

  test('shows loading state while fetching user data', () => {
    isAuthenticated.mockReturnValue(true);
    api.getMe.mockImplementation(() => new Promise(() => {})); // Never resolves
    
    renderWithRouter();
    
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  test('handles user data fetch error', async () => {
    isAuthenticated.mockReturnValue(true);
    api.getMe.mockRejectedValue(new Error('API Error'));
    
    renderWithRouter();
    
    await waitFor(() => {
      expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    });
  });
});
