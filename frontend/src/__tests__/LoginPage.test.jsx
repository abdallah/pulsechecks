import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, test, expect, vi } from 'vitest';
import LoginPage from '../pages/LoginPage';

// Mock the auth module
vi.mock('../lib/auth', () => ({
  login: vi.fn()
}));

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('LoginPage', () => {
  test('renders login page with title', () => {
    renderWithRouter(<LoginPage />);
    
    expect(screen.getByText('Pulsechecks')).toBeInTheDocument();
    expect(screen.getByText('Serverless job monitoring made simple')).toBeInTheDocument();
  });

  test('renders sign in with Google button', () => {
    renderWithRouter(<LoginPage />);
    
    expect(screen.getByText('Sign in with Google Workspace')).toBeInTheDocument();
  });

  test('renders security information', () => {
    renderWithRouter(<LoginPage />);
    
    expect(screen.getByText('Secure authentication via AWS Cognito')).toBeInTheDocument();
    expect(screen.getByText('Domain-restricted access')).toBeInTheDocument();
  });
});
