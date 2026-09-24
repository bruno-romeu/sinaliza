import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dev-time proxy for `/api` -> the FastAPI backend, mirroring the Nginx
// reverse-proxy topology used in production (ARCHITECTURE-SPINE.md AD-9) so
// the frontend never needs CORS configuration in either environment.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    pool: 'threads',
  },
})
