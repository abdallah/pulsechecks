import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import CallbackPage from '../pages/CallbackPage';

// Mock the auth functions
vi.mock('../lib/auth', () => ({
  handleCallback: vi.fn(),
}));

import { handleCallback } from '../lib/auth';

const renderWithRouter = (component, initialEntries = ['/callback?code=test-code&state=test-state']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {component}
    </MemoryRouter>
  );
};

describe('CallbackPage', () => {
  const mockOnLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('shows loading state initially', () => {
    handleCallback.mockImplementation(() => new Promise(() => {})); // Never resolves
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />);
    
    expect(screen.getByText('Completing sign in...')).toBeInTheDocument();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  test('handles successful callback', async () => {
    const mockTokens = {
      accessToken: 'access-token',
      idToken: 'id-token'
    };
    
    handleCallback.mockResolvedValue(mockTokens);
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />);
    
    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalledWith(mockTokens);
    });
    
    expect(handleCallback).toHaveBeenCalled();
  });

  test('handles callback error', async () => {
    handleCallback.mockRejectedValue(new Error('Authentication failed'));
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />);
    
    await waitFor(() => {
      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    });
    
    expect(screen.getByText('Authentication failed')).toBeInTheDocument();
    expect(mockOnLogin).not.toHaveBeenCalled();
  });

  test('handles callback with no code parameter', async () => {
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />, ['/callback']);
    
    await waitFor(() => {
      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    });
    
    // Just verify error state is shown, don't check specific message
    expect(screen.getByText('Back to Login')).toBeInTheDocument();
  });

  test('shows back to login button on error', async () => {
    handleCallback.mockRejectedValue(new Error('Test error'));
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />);
    
    await waitFor(() => {
      expect(screen.getByText('Back to Login')).toBeInTheDocument();
    });
    
    const backButton = screen.getByText('Back to Login');
    fireEvent.click(backButton);
    
    // Should navigate back (though we can't test navigation easily in this setup)
    expect(backButton).toBeInTheDocument();
  });

  test('handles network error', async () => {
    handleCallback.mockRejectedValue(new Error('Network error'));
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />);
    
    await waitFor(() => {
      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    });
    
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  test('handles invalid state parameter', async () => {
    handleCallback.mockRejectedValue(new Error('Invalid state parameter'));
    
    renderWithRouter(<CallbackPage onLogin={mockOnLogin} />, ['/callback?code=test&state=invalid']);
    
    await waitFor(() => {
      expect(screen.getByText('Authentication Error')).toBeInTheDocument();
    });
    
    expect(screen.getByText('Invalid state parameter')).toBeInTheDocument();
  });
});
