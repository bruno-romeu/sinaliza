import { expect, test } from '@playwright/test'

/**
 * Smoke test do caminho crítico: prova que a stack inteira está viva
 * (Nginx → build do React → proxy `/api` → FastAPI → PostgreSQL) e que o
 * portão de sessão do frontend funciona.
 *
 * Credenciais: usuário seed de desenvolvimento, identidade fictícia. Nenhum
 * dado real de estudante participa deste teste.
 */
const SEED_EMAIL = process.env.E2E_EMAIL ?? 'coordenacao@sinaliza.dev'
const SEED_PASSWORD = process.env.E2E_PASSWORD ?? 'change-me'

test.describe('smoke: autenticação e Home', () => {
  test('login com o usuário seed chega à Home autenticada', async ({
    page,
  }) => {
    await page.goto('/login')

    await expect(
      page.getByRole('heading', { name: 'Entrar no Sinaliza' }),
    ).toBeVisible()

    await page.getByLabel('E-mail').fill(SEED_EMAIL)
    await page.getByLabel('Senha').fill(SEED_PASSWORD)
    await page.getByRole('button', { name: 'Entrar' }).click()

    // A navegação só acontece depois de `POST /api/auth/login` responder com
    // um token: se o proxy, o backend ou o banco estiverem fora, isto falha.
    await expect(page).toHaveURL(/\/home$/)
    await expect(page.getByRole('heading', { name: 'Home' })).toBeVisible()

    // Cabeçalho autenticado: o nome vem do payload do login, não de mock.
    await expect(
      page.getByRole('button', { name: 'Sair' }).first(),
    ).toBeVisible()

    // A Home de fato carregou dados do backend (`GET /api/home`), e não só
    // renderizou o esqueleto: a seção de mudanças recentes aparece.
    await expect(
      page.getByRole('heading', { name: 'Mudanças recentes' }),
    ).toBeVisible()
  })

  test('rota protegida sem sessão redireciona para /login', async ({
    page,
  }) => {
    // Contexto novo a cada teste: `localStorage` vazio, portanto sem sessão.
    await page.goto('/home')

    await expect(page).toHaveURL(/\/login$/)
    await expect(
      page.getByRole('heading', { name: 'Entrar no Sinaliza' }),
    ).toBeVisible()
  })
})
