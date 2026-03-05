/**
 * Multi-cloud configuration for Pulsechecks frontend
 * Loads cloud-specific config based on VITE_CLOUD_PROVIDER environment variable
 *
 * Usage:
 *   AWS: VITE_CLOUD_PROVIDER=aws npm run build
 *   GCP: VITE_CLOUD_PROVIDER=gcp npm run build
 *   Default: AWS (for backward compatibility)
 */

import awsConfig from './config/aws.config'
import gcpConfig from './config/gcp.config'

// Determine cloud provider (defaults to AWS for backward compatibility)
const cloudProvider = import.meta.env.VITE_CLOUD_PROVIDER?.toLowerCase() || 'aws'

// Load appropriate configuration
let cloudConfig
if (cloudProvider === 'gcp') {
  cloudConfig = gcpConfig
} else {
  cloudConfig = awsConfig
}

// Export unified config with backward-compatible field names for AWS
export const config = {
  // Cloud provider identifier
  cloudProvider: cloudConfig.cloudProvider,

  // API URL
  apiUrl: cloudConfig.apiUrl,

  // OAuth redirect URI
  redirectUri: cloudConfig.redirectUri,

  // Auth configuration (cloud-specific)
  auth: cloudConfig.auth,

  // Backward-compatible AWS Cognito fields (for existing code)
  // These will be populated when using AWS, empty when using GCP
  cognitoRegion: cloudConfig.auth.type === 'cognito' ? cloudConfig.auth.region : '',
  cognitoUserPoolId: cloudConfig.auth.type === 'cognito' ? cloudConfig.auth.userPoolId : '',
  cognitoClientId: cloudConfig.auth.type === 'cognito' ? cloudConfig.auth.clientId : '',
  cognitoDomain: cloudConfig.auth.type === 'cognito' ? cloudConfig.auth.domain : '',

  // Firebase-specific fields (for GCP)
  firebaseConfig: cloudConfig.auth.type === 'firebase' ? cloudConfig.auth.firebaseConfig : null,
}

// Log current configuration in development
if (import.meta.env.DEV) {
  console.log('[Config] Cloud provider:', cloudProvider)
  console.log('[Config] API URL:', config.apiUrl)
  console.log('[Config] Auth type:', config.auth.type)
}
