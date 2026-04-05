import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/setupTests.js',
    // Suppress non-critical React warnings in CI
    onConsoleLog(log) {
      if (log.includes('Warning: An update') ||
          log.includes('act(...)') ||
          log.includes('coroutine')) {
        return false;
      }
    },
  },
})
