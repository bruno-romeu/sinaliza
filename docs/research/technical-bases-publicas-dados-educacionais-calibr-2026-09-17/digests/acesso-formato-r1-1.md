# Digest — Acesso e Formato: Bases Públicas de Dados Educacionais no Brasil

**Rodada:** 1 · **Data:** 2026-09-17 · **Dimensão:** Acesso e formato
**Objetivo:** calibrar gerador sintético de ~200 alunos fictícios (risco escolar) com referência estatística real.

---

## 1. Censo Escolar (INEP)

- Página oficial de microdados: `gov.br/inep/.../dados-abertos/microdados/censo-escolar`, com séries anuais disponíveis (confirmado de 1995 a 2025 nos resultados de busca), download em pacotes `.zip` por ano.
- Licença de uso do site/portal INEP (confirmada por fetch direto do rodapé da página): **Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (CC BY-ND 3.0)**. Isso é a licença geral do site institucional — não achei uma licença de dados específica e diferente (ex. Open Data Commons) documentada nas páginas acessadas.
- Segundo resultados de busca (não confirmados por fetch direto da página, que não expôs esse detalhe ao meu fetch), os microdados cobrem quatro dimensões: Escolas, Turmas, Matrículas e Docentes, disponibilizados em formato **ASCII** com "inputs" de leitura para SAS e SPSS.
- Um projeto de terceiros (GitHub, comunidade, não é fonte oficial INEP) indica que os microdados históricos do Censo Escolar (2007–2019) somam **~200 GB em CSV**, com redução de até 1/4 do tamanho ao converter para Parquet; há uma cópia espelhada em Parquet num bucket público do Google Cloud Storage (`gs://microdados-inep/microdados-censo-escolar`). Tratar como estimativa de ordem de grandeza, não número oficial.
- A página de dados abertos institucional lista "Microdados públicos do Censo Escolar da Educação Básica" também no Portal Brasileiro de Dados Abertos (`dados.gov.br`), mas o fetch direto dessa página não retornou metadados úteis (formato, licença específica, tamanho) — o conteúdo é renderizado dinamicamente e não veio no fetch estático.

## 2. SAEB (INEP)

- Página oficial: `gov.br/inep/.../dados-abertos/microdados/saeb`. O fetch direto confirmou a mesma licença institucional CC BY-ND 3.0 no rodapé, mas o corpo da página (estrutura de pastas, formato) não veio no fetch — a página parece exigir renderização client-side ou bloqueou o fetch automatizado ("conteúdo restrito"/autenticação aparente).
- Via busca (não confirmado por fetch direto — tratar como confiança média), o pacote de microdados do SAEB é organizado em sete pastas: **Dados; Dicionário; Escalas de proficiência; Inputs (R, SAS, SPSS); Leia-me e Documentos técnicos; Matrizes de Referência; Planilhas de resultados**.
- Também via busca (confiança média, não verificado por fetch direto): os arquivos de dados são fornecidos em **.csv separado por vírgula**, e o INEP descreve os arquivos como estando em "modelo simplificado, com controle de privacidade, em cumprimento à LGPD".
- Edições identificadas com microdados publicados: 2011, 2013, 2015, 2017, 2019, 2021, 2023 (cada uma com dicionário próprio).
- Não consegui confirmar tamanho/estrutura de arquivo em nível de registro (linhas, MB) do SAEB nesta rodada — ver gaps.

## 3. IDEB (INEP)

- IDEB **não é um microdado para download direto**: é um indicador calculado combinando a taxa de aprovação (do Censo Escolar) com a proficiência média no SAEB. O acesso por escola/rede/UF é feito por uma ferramenta de consulta (painel/BI) no portal do INEP, não por arquivo de microdados a nível de aluno.
- Fonte: página institucional do IDEB no INEP e nota do MEC (agosto/2026) orientando como consultar resultados do IDEB por escola via o portal (selecionar "Ideb Results" → modo "Escola").
- Implicação para o gerador sintético: IDEB serve como referência de **taxa de aprovação agregada por escola/rede**, não como fonte de distribuição aluno-a-aluno.

## 4. PNAD Educação / PNAD Contínua (IBGE)

- Dados de educação da PNAD Contínua estão disponíveis desde 2016, acessíveis pelo Portal do IBGE, pelo SIDRA (dados agregados/tabulados) e pelo Banco Multidimensional de Estatísticas (BME).
- Os microdados (nível domicílio/pessoa, amostral — não escolar/aluno individual) são distribuídos como arquivos de **texto de largura fixa (.txt/ASCII)**, com "inputs" de leitura em SAS (.sas) e um dicionário/arquivo de correspondência de variáveis. Existem conversores de terceiros para gerar CSV a partir desses arquivos de largura fixa.
- Fonte: páginas do IBGE (ibge.gov.br) — via busca, não fetch direto nesta rodada. Confiança média.
- Observação conceitual: a PNAD é uma pesquisa amostral domiciliar (nível pessoa/domicílio), não um censo de alunos matriculados — não deve ser confundida com granularidade do Censo Escolar.

## 5. LGPD, anonimização e restrição de acesso a microdados identificáveis

Este foi o achado mais relevante da rodada e responde diretamente à pergunta sobre restrições de LGPD:

- Existe um processo formal e documentado de fiscalização da **ANPD (Autoridade Nacional de Proteção de Dados)** sobre a divulgação de microdados educacionais pelo INEP (Censo Escolar e ENEM), incluindo pelo menos duas notas técnicas identificadas nos resultados de busca: uma nota técnica interna do INEP/DAES (nº 21/2022) e nota(s) técnica(s) da ANPD (referenciadas como NT 12/2023-CGF/ANPD/INEP e um documento correlato "NT-46", processo SEI 00261.000730/2022-53).
- Segundo o resumo dos resultados de busca (não li o texto completo das notas técnicas — confiança média): a área jurídica do INEP concluiu que, se a divulgação do Censo (ou outras bases) pudesse resultar em acesso a microdados pessoais não anonimizados ou permitir a reidentificação dos titulares, a divulgação **não poderia ser realizada** nos termos da LGPD.
- Em resposta, o INEP produziu **Relatórios de Impacto à Proteção de Dados Pessoais (RIPD)** tanto para os microdados do ENEM quanto para os microdados dos Censos da Educação (existe um PDF oficial "RIPD dos microdados dos Censos da Educação" hospedado em `download.inep.gov.br/microdados/`, que não consegui abrir por completo nesta rodada).
- A ANPD, segundo os resultados de busca, concluiu que o INEP endereçou adequadamente as medidas necessárias de proteção de privacidade e mitigação de risco, com critérios de divulgação desenvolvidos em parceria com a UFMG (Laboratório Inscrypt) para reduzir o risco de reidentificação.
- Existe também o **Serviço de Acesso a Dados Protegidos (Sedap)**, regido pela Portaria nº 637/2019 (atualizada pela Portaria nº 312/2023), que é o canal formal para pesquisadores acessarem bases **protegidas/não anonimizadas** do INEP mediante projeto de pesquisa aprovado (finalidade institucional/científica). O acesso ocorre em "sala segura" (presencial na sede do INEP ou, após 2023, em núcleos remotos dentro de universidades federais/institutos federais). Informação acessada no Sedap **não pode ser copiada, salva, retransmitida ou compartilhada**, em cumprimento à LGPD.
- Conclusão prática para o projeto: os microdados **públicos** (download livre) do Censo Escolar e SAEB são tratados/anonimizados antes da publicação (não permitem, em tese, identificar o aluno individual diretamente); o acesso a dados **identificados** de aluno exige passar pelo Sedap com projeto de pesquisa aprovado — não é um download direto. Isso é consistente com (mas não substitui) a leitura completa dos RIPDs, que não consegui concluir nesta rodada.

## 6. Portais estaduais/municipais

- Identifiquei apenas pela busca (sem fetch de conteúdo) a existência de portais que replicam ou linkam os microdados do Censo Escolar: "Dados Abertos SP" (`dadosabertos.des.sp.gov.br`) e o portal da SEDU-ES (`sedu.es.gov.br/microdados-do-censo-escolar`). Não investiguei se esses portais oferecem microdados próprios (com granularidade adicional) ou apenas espelham/linkam os arquivos do INEP. Fica como gap/lead para próxima rodada.

---

## Notas metodológicas desta rodada

- Diversas páginas oficiais do INEP retornaram "conteúdo restrito"/exigência de autenticação ou bloquearam o fetch automatizado (erro 401/403/ECONNRESET) mesmo sendo páginas públicas no navegador — isso limitou a confirmação direta de vários detalhes (estrutura de pastas do SAEB, texto completo das notas técnicas de LGPD). Onde isso ocorreu, marquei a confiança como média e apontei que a informação veio de síntese de busca, não de leitura direta da página primária.
- Não obtive nesta rodada números de distribuição (taxas de evasão, notas, frequência) — isso é esperado, pois o escopo desta rodada foi "acesso e formato", não os valores estatísticos em si.

