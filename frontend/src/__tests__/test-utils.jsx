import { render } from '@testing-library/react'
import { ToastProvider } from '../components/Toast'

// Custom render that includes ToastProvider
export const renderWithToast = (component) => {
  return render(
    <ToastProvider>
      {component}
    </ToastProvider>
  )
}
