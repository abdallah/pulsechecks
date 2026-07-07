import { AlertTriangle, Trash2 } from 'lucide-react'

/**
 * Reusable confirmation modal, replacing native confirm().
 *
 * Usage:
 *   const [confirmState, setConfirmState] = useState(null)
 *   setConfirmState({
 *     title: 'Delete channel',
 *     message: 'Are you sure? This cannot be undone.',
 *     confirmLabel: 'Delete',       // optional, default "Confirm"
 *     destructive: true,            // optional, red styling + trash icon
 *     onConfirm: () => { ... },
 *   })
 *   ...
 *   <ConfirmDialog state={confirmState} onClose={() => setConfirmState(null)} />
 */
export default function ConfirmDialog({ state, onClose }) {
  if (!state) return null

  const { title, message, confirmLabel = 'Confirm', destructive = false, onConfirm } = state

  function handleConfirm() {
    onClose()
    onConfirm()
  }

  const Icon = destructive ? Trash2 : AlertTriangle
  const iconWrap = destructive ? 'bg-red-100' : 'bg-amber-100'
  const iconColor = destructive ? 'text-red-600' : 'text-amber-600'
  const confirmClasses = destructive
    ? 'bg-red-600 hover:bg-red-700 focus:ring-red-300'
    : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-300'

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50" role="dialog" aria-modal="true">
      <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
        <div className="mt-3 text-center">
          <div className={`mx-auto flex items-center justify-center h-12 w-12 rounded-full ${iconWrap}`}>
            <Icon className={`h-6 w-6 ${iconColor}`} aria-hidden="true" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mt-4">{title}</h3>
          <div className="mt-2 px-7 py-3">
            <p className="text-sm text-gray-500">{message}</p>
          </div>
          <div className="items-center px-4 py-3">
            <button
              onClick={handleConfirm}
              className={`px-4 py-2 text-white text-base font-medium rounded-md w-full shadow-sm focus:outline-none focus:ring-2 ${confirmClasses}`}
            >
              {confirmLabel}
            </button>
            <button
              onClick={onClose}
              className="mt-3 px-4 py-2 bg-white text-gray-500 text-base font-medium rounded-md w-full shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
