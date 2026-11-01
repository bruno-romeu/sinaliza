import { configDefaults, defineConfig } from 'vitest/config'
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
    // Os testes unitários vivem em `src/`; `e2e/` é do Playwright. Sem esta
    // exclusão o padrão de descoberta do Vitest pegaria `e2e/**/*.spec.ts` e
    // quebraria `npm test` (os globais do Playwright não existem no Vitest).
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
