import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// `npm run dev:mock` (mode "mock") adds an in-process fake backend so the
// whole app runs with realistic fixture data and no cloud/auth setup —
// see mock/README.md. Never included in `npm run build`.
export default defineConfig(async ({ mode }) => {
  const plugins = [react()]

  if (mode === 'mock') {
    const { mockApiPlugin } = await import('./mock/server.js')
    plugins.push(mockApiPlugin())
  }

  return {
    plugins,
    server: {
      port: 3000,
    },
  }
})
