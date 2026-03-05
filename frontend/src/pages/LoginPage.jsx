import { Activity } from 'lucide-react'
import { login } from '../lib/auth'

export default function LoginPage() {
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
            onClick={login}
            className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Sign in with Google Workspace
          </button>
          
          <div className="text-center text-xs text-gray-500">
            <p>Secure authentication via AWS Cognito</p>
            <p className="mt-1">Domain-restricted access</p>
          </div>
        </div>
      </div>
    </div>
  )
}
