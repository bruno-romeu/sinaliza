import { configDefaults, defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dev-time proxy for `/api` -> the FastAPI backend, mirroring the Nginx
// reverse-proxy topology used in production (ARCHITECTURE-SPINE.md AD-9) so
// the frontend never needs CORS configuration in either environment.
//
// O alvo e configuravel por `VITE_API_PROXY_TARGET` porque o endereco do
// backend e um fato do ambiente, nao do projeto: com o alvo fixo, duas
// pessoas (ou dois agentes) nao conseguem rodar `vite dev` ao mesmo tempo,
// ja que ambos precisariam do mesmo `localhost:8000`. O default preserva
// exatamente o comportamento anterior, entao quem nao define a variavel nao
// percebe diferenca.
//
// `rewrite` tira o prefixo `/api` porque o uvicorn local serve as rotas na
// raiz. Um alvo que ja faca esse strip — o Nginx da stack do docker compose,
// em `http://localhost` — precisa do prefixo preservado, e para esse caso
// existe `VITE_API_PROXY_KEEP_PREFIX=true`.
const apiProxyTarget =
  process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
const keepApiPrefix = process.env.VITE_API_PROXY_KEEP_PREFIX === 'true'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: keepApiPrefix
          ? undefined
          : (path) => path.replace(/^\/api/, ''),
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
