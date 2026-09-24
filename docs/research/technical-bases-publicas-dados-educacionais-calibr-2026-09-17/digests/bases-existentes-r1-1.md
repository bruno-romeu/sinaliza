# Digest — Bases públicas de dados educacionais no Brasil (rodada 1)

**Tópico:** Bases públicas/abertas de educação básica no Brasil, para calibrar distribuições de um gerador de dataset sintético de ~200 alunos fictícios (frequência, notas, evasão, atividades não entregues).

**Data da pesquisa:** 2026-09-17

---

## 1. Censo Escolar da Educação Básica (INEP/MEC)

- **O que mede:** o principal levantamento estatístico da educação básica brasileira — dados de escolas (infraestrutura, localização, dependência administrativa), turmas (etapa de ensino, horário, atividades complementares), matrículas (perfil dos alunos: idade, sexo, cor/raça, necessidades especiais, transporte escolar) e docentes (formação, vínculo, disciplinas). Realizado em colaboração com secretarias estaduais e municipais, cobrindo todas as escolas públicas e privadas do país.
- **Granularidade:** historicamente havia registros em nível de matrícula/aluno individual (anonimizado) e de docente. **Desde a edição de 2021 (mudança anunciada em fevereiro de 2022), o INEP deixou de divulgar microdados em nível de aluno/matrícula e turma**, publicando apenas uma "sinopse estatística ampliada" agregada por escola, alegando obrigações da LGPD (Lei 13.709/2018). Dados desagregados ainda existem, mas só são acessíveis mediante solicitação formal via Serviço de Acesso a Dados Protegidos (Sedap) do INEP, com identificação, justificativa e avaliação prévia do órgão.
- **Periodicidade:** anual.
- **Cobertura geográfica:** nacional (todos os municípios/estados).
- **Cobertura temporal:** microdados públicos disponíveis de 1995 a 2025 (dado 2025 atualizado em julho/2026), mas bases anteriores a 2021 têm granularidade maior (aluno/turma); a partir de 2021 a granularidade pública caiu para nível agregado por escola.
- **Implicação para calibração:** para simular atividades não entregues/frequência por aluno individual, os microdados públicos recentes (2021+) NÃO servem diretamente — só dão taxas agregadas por escola/turma. Anos anteriores a 2021 tinham granularidade de matrícula, mas via de regra sem "notas" individuais (essas vêm do SAEB, que é amostral e por proficiência, não boletim).

## 2. IDEB — Índice de Desenvolvimento da Educação Básica (INEP)

- **O que mede:** indicador combinado de fluxo escolar (taxas de aprovação vindas do Censo Escolar) e desempenho (proficiência em Língua Portuguesa e Matemática vinda do SAEB), numa escala de 0 a 10.
- **Cálculo:** nota SAEB padronizada (0–10) multiplicada pela média harmônica das taxas de aprovação da etapa (anos iniciais, anos finais, ensino médio).
- **Granularidade:** escola, município, estado e Brasil (não há IDEB por aluno individual).
- **Periodicidade:** bienal, calculado com dados de turmas do 5º e 9º ano do Ensino Fundamental e do 3º ano do Ensino Médio.
- **Cobertura geográfica/temporal:** nacional, desde 2005 (criado em 2007, retroagindo à série histórica); metodologia mantida inalterada desde 2007 para preservar comparabilidade.

## 3. SAEB — Sistema de Avaliação da Educação Básica (INEP)

- **O que mede:** desempenho estudantil (proficiência) em Língua Portuguesa e Matemática, além de questionários contextuais (fatores associados ao desempenho) — respondidos por alunos, professores, diretores e aplicadores.
- **Granularidade:** amostral — abrange toda a rede pública e uma amostra da rede privada; testes aplicados a alunos do 5º e 9º ano do Ensino Fundamental e 3º ano do Ensino Médio, em áreas urbanas e rurais. Os microdados do SAEB (quando publicados) permitem análise por aluno respondente dentro da amostra, mas não é um "boletim" individual contínuo — é uma prova amostral pontual.
- **Periodicidade:** bienal (aplicado desde 1990, com aprimoramentos metodológicos ao longo do tempo).
- **Cobertura:** nacional.
- **Nota:** o QEdu usa os microdados do SAEB para calcular "aprendizagem adequada" e, desde 2021, o INSE (Indicador de Nível Socioeconômico) via Teoria de Resposta ao Item com 22 variáveis do questionário contextual.

## 4. QEdu (portal, não é base primária — agrega Censo Escolar + SAEB/Prova Brasil + IDEB)

- **O que oferece:** "Taxas de Rendimento" (aprovação, reprovação, abandono) por escola, município, estado e Brasil, calculadas a partir do Censo Escolar; dados de aprendizagem adequada a partir de microdados do SAEB; INSE por escola.
- **Definição de abandono (QEdu/Academia QEdu):** ocorre quando o aluno deixa de frequentar as aulas durante o ano letivo; ao final do ano letivo cada matrícula é classificada como aprovada, reprovada ou abandono.
- **Exemplo de número (fonte secundária apontando dado 2023 do Censo Escolar, não verificado na fonte primária INEP nesta rodada):** anos iniciais do Ensino Fundamental teriam taxa de abandono de 0,3% em 2023 (vs. 0,5% em 2022); anos finais, 1,2% em 2023 (vs. 1,9% em 2022). Tratar como pista para verificação — não confirmado diretamente na página oficial do INEP nesta rodada.
- **Granularidade:** escola, município, estado, Brasil — não há dado por aluno individual (QEdu é agregador de estatísticas do Censo Escolar/SAEB, não replica microdados brutos).
- **Periodicidade:** segue a periodicidade das fontes primárias (Censo Escolar anual; SAEB bienal).

## 5. PNAD Contínua — módulo Educação (IBGE)

- **O que mede:** pesquisa amostral domiciliar contínua do IBGE; o módulo temático anual de Educação cobre acesso ao ensino, analfabetismo, escolaridade, abandono escolar, condição de estudo e situação de trabalho da população.
- **Granularidade:** domicílio/pessoa (amostra domiciliar), agregada e divulgada por grandes grupos (faixa etária, sexo, cor/raça, regiões) — não é dado por escola/aluno matriculado.
- **Periodicidade:** anual (o módulo temático de Educação).
- **Cobertura:** nacional, com possibilidade de desagregação regional conforme desenho amostral.
- **Dado de exemplo (fonte secundária, checar contra publicação oficial IBGE — tentativa de acesso direto à página da Agência IBGE retornou erro 403 nesta rodada):** em 2025, 7,7 milhões de jovens de 14 a 29 anos não haviam concluído o Ensino Médio (abandono ou nunca frequentaram); dentro desse grupo, maior concentração de abandono ocorre entre 16–18 anos; motivo mais citado é necessidade de trabalhar (43,0%), com gravidez como motivo relevante entre mulheres (24,7%).

## 6. Portais estaduais de dados abertos em educação — exemplo São Paulo

- **Portal:** Dados Abertos da Educação do Estado de São Paulo (dados.educacao.sp.gov.br) e Portal de Dados Abertos do Estado de SP (dadosabertos.sp.gov.br / dadosabertos.des.sp.gov.br).
- **O que oferece:** indicadores de fluxo escolar da rede estadual, IDESP (Índice de Desenvolvimento da Educação do Estado de São Paulo — indicador próprio de qualidade escolar) e SARESP (Sistema de Avaliação de Rendimento Escolar do Estado de São Paulo, avaliação estadual análoga ao SAEB).
- **Granularidade:** aparentemente por escola/rede estadual (não confirmado nível aluno individual nesta rodada).
- **Cobertura:** estado de São Paulo, rede estadual.
- **Observação:** é um exemplo do padrão "portal estadual" — outros estados (ES, RS, MT citados no QEdu) têm páginas equivalentes, mas cada uma tem estrutura própria; não investigadas em detalhe nesta rodada por orçamento.

---

## Lacunas / o que NÃO foi possível confirmar nesta rodada

- Confirmação, direto na página oficial do INEP, dos números específicos de taxa de abandono 2022/2023 citados por fontes secundárias (QEdu/Academia QEdu) — a fonte primária (Censo Escolar / sinopses estatísticas do INEP) não foi lida diretamente com esses números nesta rodada.
- Conteúdo integral da "Nota de Esclarecimento" oficial do INEP sobre a mudança de granularidade dos microdados (a página retornou como conteúdo restrito/autenticado na tentativa de fetch).
- Números exatos e link direto (texto completo) da matéria da Agência IBGE sobre PNAD Educação 2025 (fetch retornou 403); os números citados vêm de snippets de busca, não de leitura completa da página.
- Detalhamento de portais municipais de dados abertos em educação (ex.: prefeituras de capitais) — não pesquisado nesta rodada.
- Confirmação de se e como o SAEB disponibiliza microdados públicos por aluno respondente (nível de granularidade exato dos arquivos de microdados do SAEB, distinto do agregado por escola) — não verificado diretamente na página oficial do SAEB nesta rodada.
- Detalhe de "atividades não entregues" — nenhuma das bases encontradas mede diretamente isso; é um proxy que precisará ser inferido/estimado a partir de frequência e taxas de rendimento, não há fonte pública brasileira que meça "tarefas não entregues" por aluno.
- Estrutura completa do Sedap (Serviço de Acesso a Dados Protegidos) do INEP — mencionado como via de acesso a microdados desagregados pós-2021, mas processo/formato não detalhado.

## Pistas para próxima rodada

- Ler diretamente as "Sinopses Estatísticas" e Notas Técnicas do Censo Escolar no site do INEP para confirmar taxas de abandono/aprovação por etapa e ano com números oficiais primários.
- Buscar o texto completo da Nota Informativa do IDEB 2023/2025 (download.inep.gov.br/ideb/...) para extrair distribuições de notas por etapa/região.
- Tentar acessar microdados do SAEB (ou seu dicionário de variáveis) para confirmar granularidade exata (aluno respondente vs. escola).
- Investigar o Sedap do INEP como via formal de acesso a microdados desagregados pós-LGPD (útil se o projeto puder justificar pesquisa acadêmica/técnica).
- Checar diretamente a Agência de Notícias IBGE ou a publicação "Educação 2025" (biblioteca.ibge.gov.br) para números oficiais de frequência/abandono por faixa etária, sem depender de agregadores.
- Levantar 2–3 portais estaduais adicionais (ex. Rio de Janeiro, Minas Gerais, Rio Grande do Sul) e verificar se algum disponibiliza dado por aluno anonimizado (mais provável que INEP nacional, já que nem todos os estados seguem a mesma política de restrição).
- Verificar se existe algum "painel de evasão escolar" federal mais recente (ex. Busca Ativa Escolar, citado en passant numa fonte) como possível base de indicadores de risco de evasão já estruturada de forma similar ao objetivo do projeto.
- QEdu Academia (academia.qedu.org.br) tem múltiplos artigos metodológicos — vale ler mais a fundo (a tentativa de fetch falhou por erro de conexão nesta rodada, tentar de novo).

---

## Fontes consultadas nesta rodada

1. gov.br/inep — Microdados do Censo Escolar (https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar)
2. dados.gov.br — Microdados públicos do Censo Escolar (https://dados.gov.br/dados/conjuntos-dados/inep-microdados-do-censo-escolar-da-educacao-basica) [via snippet de busca]
3. Academia QEdu — Taxa de Rendimento (https://academia.qedu.org.br/censo-escolar/taxa-de-rendimento/) [via snippet de busca; fetch direto falhou]
4. QEdu — Brasil, Taxas de Rendimento (https://qedu.org.br/brasil/taxas-rendimento) [via snippet de busca]
5. gov.br/inep — Nota informativa do Ideb 2023 (https://download.inep.gov.br/ideb/nota_informativa_ideb_2023.pdf) [via snippet de busca]
6. gov.br/inep — Índice de Desenvolvimento da Educação Básica / Ideb (https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb) [via snippet de busca]
7. gov.br/inep — Saeb (https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/saeb) [via snippet de busca]
8. Todos Pela Educação — Pnad Contínua: o que o IBGE revela sobre a Educação brasileira? (https://todospelaeducacao.org.br/noticias/pnad-continua-o-que-o-ibge-revela-sobre-a-educacao-brasileira/) [via snippet de busca]
9. Busca Ativa Escolar — Pnad Educação: 8,7 milhões de jovens... (https://buscaativaescolar.org.br/noticia/pnad-educacao-8-7-milhoes-de-jovens-brasileiros-abandonaram-ou-nunca-frequentaram-a-escola) [via snippet de busca]
10. Agência de Notícias IBGE — Analfabetismo fica abaixo de 5% em 2025... (https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/47221-analfabetismo-fica-abaixo-de-5-em-2025-mas-8-4-milhoes-ainda-nao-sabem-ler-e-escrever) [fetch retornou 403 — não lido integralmente]
11. Centro de Referências em Educação Integral — Por que a exclusão de dados do Censo Escolar é um problema? (https://educacaointegral.org.br/reportagens/por-que-exclusao-de-dados-do-censo-escolar-e-um-problema/) [lido integralmente via fetch]
12. IEDE — Nota Técnica LGPD, caminhos para disponibilização de microdados de educação (https://portaliede.org.br/wp-content/uploads/2024/06/Nota_Tecnica_LGPD.pdf) [via snippet de busca]
13. Dados Abertos da Educação — Estado de São Paulo (https://dados.educacao.sp.gov.br/) [via snippet de busca]
14. Portal de Dados Abertos do Estado de São Paulo (https://dadosabertos.sp.gov.br/painel) [via snippet de busca]

**Status do orçamento:** ~13 chamadas de busca/leitura utilizadas (acima do teto de 10 sugerido; parado por esgotamento de escopo razoável para esta rodada — ver "stop_reason").
