import { Activity, LogOut, Share2, ChevronRight } from 'lucide-react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { logout } from '../lib/auth'

/**
 * App shell with top navigation and an optional breadcrumb trail.
 *
 * Pages pass `breadcrumbs` as [{ label, to }] — the last crumb is the
 * current page and renders without a link:
 *   <Layout breadcrumbs={[{ label: 'Teams', to: '/' }, { label: team.name }]}>
 */
export default function Layout({ user, onLogout, breadcrumbs, children }) {
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    onLogout()
    logout()
  }

  const navLinks = [
    { label: 'Dashboard', to: '/' },
    { label: 'Shared Alerts', to: '/shared-alerts', Icon: Share2 },
  ]

  function isActive(to) {
    if (to === '/') return location.pathname === '/'
    return location.pathname.startsWith(to)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center space-x-6">
              <div className="flex items-center cursor-pointer" onClick={() => navigate('/')}>
                <Activity className="h-8 w-8 text-blue-600" aria-hidden="true" />
                <span className="ml-2 text-xl font-bold text-gray-900">Pulsechecks</span>
              </div>
              {user && (
                <div className="hidden sm:flex items-center space-x-1">
                  {navLinks.map(({ label, to, Icon }) => (
                    <Link
                      key={to}
                      to={to}
                      aria-current={isActive(to) ? 'page' : undefined}
                      className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                        isActive(to)
                          ? 'text-blue-700 bg-blue-50'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`}
                    >
                      {Icon && <Icon className="h-4 w-4 mr-1.5" aria-hidden="true" />}
                      {label}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {user && (
              <div className="flex items-center space-x-4">
                <span className="text-sm text-gray-700">{user.email}</span>
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <LogOut className="h-4 w-4 mr-2" aria-hidden="true" />
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      {breadcrumbs && breadcrumbs.length > 0 && (
        <div className="bg-white border-b border-gray-100">
          <nav aria-label="Breadcrumb" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
            <ol className="flex items-center flex-wrap text-sm">
              {breadcrumbs.map((crumb, i) => {
                const isLast = i === breadcrumbs.length - 1
                return (
                  <li key={`${crumb.label}-${i}`} className="flex items-center min-w-0">
                    {i > 0 && <ChevronRight className="h-4 w-4 mx-1.5 text-gray-300 flex-shrink-0" aria-hidden="true" />}
                    {isLast || !crumb.to ? (
                      <span className="text-gray-700 font-medium truncate" aria-current="page">{crumb.label}</span>
                    ) : (
                      <Link to={crumb.to} className="text-gray-500 hover:text-gray-700 hover:underline truncate">
                        {crumb.label}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ol>
          </nav>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
