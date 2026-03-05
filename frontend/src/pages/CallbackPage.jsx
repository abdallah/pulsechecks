import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { handleCallback } from '../lib/auth'

export default function CallbackPage({ onLogin }) {
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  
  useEffect(() => {
    async function processCallback() {
      try {
        const tokens = await handleCallback()
        onLogin(tokens)
        navigate('/', { replace: true })
      } catch (err) {
        console.error('Callback error:', err)
        setError(err.message)
      }
    }
    
    processCallback()
  }, [navigate, onLogin])
  
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <h3 className="text-sm font-medium text-red-800">Authentication Error</h3>
            <p className="mt-2 text-sm text-red-700">{error}</p>
          </div>
          <button
            onClick={() => navigate('/login')}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700"
          >
            Back to Login
          </button>
        </div>
      </div>
    )
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing sign in...</p>
      </div>
    </div>
  )
}
