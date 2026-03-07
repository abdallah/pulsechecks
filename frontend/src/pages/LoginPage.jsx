import { Activity } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, handleCallback } from '../lib/auth'
import { config } from '../config'

export default function LoginPage({ onLogin = () => {} }) {
  const navigate = useNavigate()
  const [loginError, setLoginError] = useState(null)

  async function handleSignIn() {
    setLoginError(null)

    try {
      const tokens = await login()
      if (tokens) {
        onLogin(tokens)
        navigate('/', { replace: true })
      }
    } catch (error) {
      console.error('Login failed:', error)
      setLoginError(error?.message || 'Sign in failed')
    }
  }

  useEffect(() => {
    async function processFirebaseRedirect() {
      if (config.auth.type !== 'firebase') {
        return
      }

      try {
        const tokens = await handleCallback()
        if (tokens) {
          onLogin(tokens)
          navigate('/', { replace: true })
        }
      } catch (error) {
        console.error('Firebase redirect processing failed:', error)
      }
    }

    processFirebaseRedirect()
  }, [navigate, onLogin])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <div className="flex justify-center">
            <Activity className="h-12 w-12 text-blue-600" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Pulsechecks
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Serverless job monitoring made simple
          </p>
        </div>
        
        <div className="mt-8 space-y-6">
          <button
            onClick={handleSignIn}
            className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Sign in with Google Workspace
          </button>

          {loginError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">
              {loginError}
            </div>
          )}
          
          <div className="text-center text-xs text-gray-500">
            <p>Secure authentication via {config.auth.type === 'firebase' ? 'Firebase Auth' : 'AWS Cognito'}</p>
            <p className="mt-1">Domain-restricted access</p>
          </div>
        </div>
      </div>
    </div>
  )
}
