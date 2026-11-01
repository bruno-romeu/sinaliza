import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright end-to-end (Onda 0, entrada 0.4).
 *
 * Os testes rodam contra a stack já levantada por `docker compose` — Nginx
 * servindo o build do React e fazendo proxy de `/api` para o FastAPI, a mesma
 * topologia descrita em `frontend/nginx.conf`. Não há `webServer` aqui de
 * propósito: o smoke test só tem valor se exercitar a stack inteira (front +
 * proxy + backend + banco), não um `vite dev` isolado.
 *
 * `E2E_BASE_URL` permite apontar para outro host (ex.: um runner de CI que
 * publique a porta em outro lugar) sem editar este arquivo.
 */
export default defineConfig({
  testDir: './e2e',
  // Sem testes marcados como `.only` esquecidos no CI.
  forbidOnly: !!process.env.CI,
  // Local: zero retentativas, para que teste intermitente apareça como falha
  // em vez de ser escondido por um retry silencioso.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  // Teto por teste: uma asserção web-first que nunca resolve falha rápido em
  // vez de travar o pipeline.
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  // Só Chromium: este é um smoke test de stack viva, não uma matriz de
  // compatibilidade entre navegadores.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
