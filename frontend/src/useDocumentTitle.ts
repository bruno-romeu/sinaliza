import { useEffect } from 'react'

const APP_NAME = 'Sinaliza'

/**
 * Dá a cada rota o seu próprio `document.title`.
 *
 * Numa SPA o `<title>` do `index.html` vale para a aplicação inteira: a
 * medição encontrou `"Sinaliza"` nas oito rotas. Quem navega por leitor de
 * tela recebe o título ao chegar numa página, então um título único por tela
 * é a única pista de "onde eu estou" nessa travessia (WCAG 2.4.2). O mesmo
 * título também é o que aparece no histórico do navegador e na aba.
 *
 * `screen` é o nome da tela, não uma frase; o nome da aplicação é anexado
 * aqui para que nenhuma página precise repeti-lo. `null` enquanto a tela
 * ainda não sabe o próprio nome (ex.: o estudante ainda carregando).
 */
export function useDocumentTitle(screen: string | null): void {
  useEffect(() => {
    document.title = screen ? `${screen} · ${APP_NAME}` : APP_NAME
  }, [screen])
}
