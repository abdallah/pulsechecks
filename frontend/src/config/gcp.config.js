/**
 * GCP-specific configuration for Pulsechecks frontend
 * Uses Firebase Authentication for user authentication
 */

export const gcpConfig = {
  // Cloud provider identifier
  cloudProvider: 'gcp',

  // API endpoint (Cloud Run service URL)
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:8080',

  // Firebase configuration
  auth: {
    type: 'firebase',
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',

    // Firebase config object (used by Firebase SDK)
    firebaseConfig: {
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
    },
  },

  // OAuth redirect URI (handled by Firebase)
  redirectUri: import.meta.env.VITE_REDIRECT_URI || (
    window.location.hostname === 'localhost'
      ? 'http://localhost:3000/callback'
      : `${window.location.origin}/callback`
  ),
}

export default gcpConfig
