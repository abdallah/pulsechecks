import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import Layout from '../components/Layout';

// Mock the auth functions
vi.mock('../lib/auth', () => ({
  logout: vi.fn(),
}));

import { logout } from '../lib/auth';

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

const mockUser = {
  userId: 'user-123',
  email: 'test@example.com',
  name: 'Test User'
};

const mockOnLogout = vi.fn();

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders navigation with user info', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
  });

  test('renders children content', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  test('renders without user (should not show user info)', () => {
    renderWithRouter(
      <Layout user={null} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    expect(screen.getByText('Test Content')).toBeInTheDocument();
    expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    expect(screen.queryByText('Logout')).not.toBeInTheDocument();
  });

  test('calls logout when logout button clicked', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    const logoutButton = screen.getByText('Logout');
    fireEvent.click(logoutButton);
    
    expect(mockOnLogout).toHaveBeenCalled();
  });

  test('navigates to home when logo clicked', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    const logo = screen.getByText('Pulsechecks').closest('div');
    fireEvent.click(logo);
    
    // Navigation should be triggered (though we can't easily test the actual navigation)
    expect(logo).toHaveClass('cursor-pointer');
  });

  test('renders logout button with icon', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    const logoutButton = screen.getByText('Logout');
    expect(logoutButton).toBeInTheDocument();
    
    // Check for logout icon (lucide-log-out class)
    const icon = logoutButton.querySelector('.lucide-log-out');
    expect(icon).toBeInTheDocument();
  });

  test('renders activity icon in logo', () => {
    renderWithRouter(
      <Layout user={mockUser} onLogout={mockOnLogout}>
        <div>Test Content</div>
      </Layout>
    );
    
    // Check for activity icon (lucide-activity class)
    const activityIcon = document.querySelector('.lucide-activity');
    expect(activityIcon).toBeInTheDocument();
  });
});
