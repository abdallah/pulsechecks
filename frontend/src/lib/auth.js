/**
 * Multi-cloud authentication module
 * Supports both AWS Cognito and Firebase Authentication
 */

import { config } from '../config'

// ============================================================================
// Cognito-specific implementation (AWS)
// ============================================================================

function generateCodeVerifier() {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return base64URLEncode(array)
}

function base64URLEncode(buffer) {
  const base64 = btoa(String.fromCharCode(...buffer))
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

async function generateCodeChallenge(verifier) {
  const encoder = new TextEncoder()
  const data = encoder.encode(verifier)
  const hash = await crypto.subtle.digest('SHA-256', data)
  return base64URLEncode(new Uint8Array(hash))
}

function generateState() {
  const array = new Uint8Array(16)
  crypto.getRandomValues(array)
  return base64URLEncode(array)
}

async function cognitoLogin() {
  const codeVerifier = generateCodeVerifier()
  const codeChallenge = await generateCodeChallenge(codeVerifier)
  const state = generateState()

  sessionStorage.setItem('pkce_code_verifier', codeVerifier)
  sessionStorage.setItem('oauth_state', state)

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: config.cognitoClientId,
    redirect_uri: config.redirectUri,
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    scope: 'openid email profile',
  })

  const loginUrl = `${config.cognitoDomain}/oauth2/authorize?${params}`
  window.location.href = loginUrl
}

async function cognitoHandleCallback() {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  const state = params.get('state')
  const error = params.get('error')

  if (error) {
    throw new Error(`OAuth error: ${error}`)
  }

  if (!code) {
    throw new Error('No authorization code received')
  }

  const savedState = sessionStorage.getItem('oauth_state')
  console.log('State verification:', { received: state, saved: savedState })

  if (!savedState) {
    console.warn('No saved state found in sessionStorage')
  } else if (state !== savedState) {
    console.error('State mismatch:', { received: state, saved: savedState })
    throw new Error('Invalid state parameter')
  }

  const codeVerifier = sessionStorage.getItem('pkce_code_verifier')

  if (!codeVerifier) {
    console.error('No code verifier found in sessionStorage')
    throw new Error('Authentication session expired. Please try logging in again.')
  }

  const tokenParams = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: config.cognitoClientId,
    code: code,
    redirect_uri: config.redirectUri,
    code_verifier: codeVerifier,
  })

  console.log('Token exchange params:', Object.fromEntries(tokenParams))
  console.log('Code verifier from storage:', codeVerifier)

  const response = await fetch(`${config.cognitoDomain}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: tokenParams,
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error('Token exchange failed:', response.status, errorText)
    throw new Error(`Failed to exchange code for tokens: ${response.status} ${errorText}`)
  }

  const tokens = await response.json()

  sessionStorage.removeItem('pkce_code_verifier')
  sessionStorage.removeItem('oauth_state')

  return tokens
}

function cognitoLogout() {
  const params = new URLSearchParams({
    client_id: config.cognitoClientId,
    logout_uri: window.location.origin,
  })

  window.location.href = `${config.cognitoDomain}/logout?${params}`
}

// ============================================================================
// Firebase-specific implementation (GCP)
// ============================================================================

let firebaseAuth = null

async function initFirebase() {
  if (firebaseAuth) return firebaseAuth

  const { initializeApp } = await import('firebase/app')
  const { getAuth, GoogleAuthProvider } = await import('firebase/auth')

  const app = initializeApp(config.firebaseConfig)
  firebaseAuth = getAuth(app)

  return firebaseAuth
}

async function firebaseLogin() {
  const auth = await initFirebase()
  const { signInWithPopup, signInWithRedirect, GoogleAuthProvider } = await import('firebase/auth')

  const provider = new GoogleAuthProvider()
  provider.addScope('email')
  provider.addScope('profile')

  try {
    const result = await signInWithPopup(auth, provider)
    if (!result?.user) {
      return null
    }

    const idToken = await result.user.getIdToken()
    return {
      id_token: idToken,
      access_token: idToken,
    }
  } catch (error) {
    const popupErrors = new Set([
      'auth/popup-blocked',
      'auth/popup-closed-by-user',
      'auth/cancelled-popup-request',
    ])

    if (popupErrors.has(error?.code)) {
      await signInWithRedirect(auth, provider)
      return null
    }

    throw error
  }
}

async function firebaseHandleCallback() {
  const auth = await initFirebase()
  const { getRedirectResult } = await import('firebase/auth')

  const result = await getRedirectResult(auth)

  if (!result) {
    return null
  }

  // Get ID token from Firebase
  const idToken = await result.user.getIdToken()

  // Return in Cognito-compatible format
  return {
    id_token: idToken,
    access_token: idToken, // Firebase uses ID token as access token
  }
}

async function firebaseLogout() {
  const auth = await initFirebase()
  const { signOut } = await import('firebase/auth')

  await signOut(auth)
  clearTokens()
  window.location.href = window.location.origin
}

// ============================================================================
// Public API (cloud-agnostic)
// ============================================================================

export async function login() {
  if (config.auth.type === 'firebase') {
    return firebaseLogin()
  } else {
    return cognitoLogin()
  }
}

export async function handleCallback() {
  if (config.auth.type === 'firebase') {
    return firebaseHandleCallback()
  } else {
    return cognitoHandleCallback()
  }
}

export async function logout() {
  if (config.auth.type === 'firebase') {
    return firebaseLogout()
  } else {
    return cognitoLogout()
  }
}

// Token storage (cloud-agnostic)
export function setTokens(tokens) {
  localStorage.setItem('access_token', tokens.access_token)
  if (tokens.id_token) {
    localStorage.setItem('id_token', tokens.id_token)
  }
}

export function getAccessToken() {
  return localStorage.getItem('access_token')
}

export function getIdToken() {
  return localStorage.getItem('id_token')
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('id_token')
}

export function isAuthenticated() {
  return !!localStorage.getItem('id_token')
}
