import { describe, test, expect, vi, beforeEach } from 'vitest'

vi.mock('../config', () => ({
  config: {
    auth: { type: 'cognito' },
    cognitoClientId: 'test-client-id',
    cognitoDomain: 'https://example.auth.us-east-1.amazoncognito.com',
    redirectUri: 'http://localhost:3000/callback',
  },
}))

import { handleCallback } from '../lib/auth'

describe('Cognito OAuth callback', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    global.fetch.mockReset()
    window.history.pushState({}, '', '/callback')
  })

  test('fails closed when oauth_state is missing', async () => {
    sessionStorage.setItem('pkce_code_verifier', 'verifier-123')
    window.history.pushState({}, '', '/callback?code=test-code&state=test-state')

    await expect(handleCallback()).rejects.toThrow('Missing OAuth state parameter')
    expect(global.fetch).not.toHaveBeenCalled()
  })

  test('fails when state does not match saved oauth_state', async () => {
    sessionStorage.setItem('pkce_code_verifier', 'verifier-123')
    sessionStorage.setItem('oauth_state', 'expected-state')
    window.history.pushState({}, '', '/callback?code=test-code&state=wrong-state')

    await expect(handleCallback()).rejects.toThrow('Invalid state parameter')
    expect(global.fetch).not.toHaveBeenCalled()
  })

  test('continues with a valid state and preserves PKCE exchange behavior', async () => {
    sessionStorage.setItem('pkce_code_verifier', 'verifier-123')
    sessionStorage.setItem('oauth_state', 'expected-state')
    window.history.pushState({}, '', '/callback?code=test-code&state=expected-state')

    global.fetch.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ access_token: 'access-token', id_token: 'id-token' }),
    })

    await expect(handleCallback()).resolves.toEqual({ access_token: 'access-token', id_token: 'id-token' })

    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('pkce_code_verifier')).toBeNull()
    expect(sessionStorage.getItem('oauth_state')).toBeNull()
  })
})
