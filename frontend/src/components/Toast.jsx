import { useState, useCallback, useMemo, createContext, useContext } from 'react'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'

const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
}

const STYLES = {
  success: 'bg-green-50 border-green-400 text-green-800',
  error: 'bg-red-50 border-red-400 text-red-800',
  info: 'bg-blue-50 border-blue-400 text-blue-800',
}

const DISMISS_MS = { success: 3000, error: 5000, info: 4000 }

let toastId = 0

const ToastContext = createContext()

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback((message, type = 'info') => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => removeToast(id), DISMISS_MS[type] || 4000)
  }, [removeToast])

  const toast = useMemo(() => ({
    success: (msg) => showToast(msg, 'success'),
    error: (msg) => showToast(msg, 'error'),
    info: (msg) => showToast(msg, 'info'),
    show: showToast,
  }), [showToast])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map(({ id, message, type }) => {
          const Icon = ICONS[type]
          return (
            <div
              key={id}
              role="alert"
              className={`flex items-start gap-2 border-l-4 p-3 rounded shadow-md animate-[slideIn_0.2s_ease-out] ${STYLES[type]}`}
            >
              <Icon className="h-5 w-5 shrink-0 mt-0.5" />
              <span className="text-sm flex-1">{message}</span>
              <button
                onClick={() => removeToast(id)}
                className="shrink-0 hover:opacity-70"
                aria-label="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
