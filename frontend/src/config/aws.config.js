/**
 * AWS-specific configuration for Pulsechecks frontend
 * Uses AWS Cognito for authentication
 */

export const awsConfig = {
  // Cloud provider identifier
  cloudProvider: 'aws',

  // API endpoint (AWS API Gateway or Lambda Function URL)
  apiUrl: import.meta.env.VITE_API_URL || 'http://localhost:3001',

  // AWS Cognito configuration
  auth: {
    type: 'cognito',
    region: import.meta.env.VITE_COGNITO_REGION || 'us-east-1',
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
    clientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '',
    domain: import.meta.env.VITE_COGNITO_DOMAIN || '',
  },

  // OAuth redirect URI
  redirectUri: import.meta.env.VITE_REDIRECT_URI || (
    window.location.hostname === 'localhost'
      ? 'http://localhost:3000/callback'
      : `${window.location.origin}/callback`
  ),
}

export default awsConfig
