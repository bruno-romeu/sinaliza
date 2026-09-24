# Limitações e vieses das bases públicas educacionais brasileiras — Rodada 2 (aprofundamento)

Data da pesquisa: 2026-09-17
Objetivo: fechar lacunas da Rodada 1 sobre defasagem de publicação, autodeclaração na PNAD, mudanças de metodologia do SAEB/IDEB e taxa de adesão de escolas privadas ao SAEB.

## Sumário executivo

Esta rodada conseguiu quantificar, com fontes primárias (MEC/INEP), a defasagem estrutural entre ano de referência e publicação definitiva dos dados — algo entre ~9 e ~12 meses, confirmado tanto no cronograma do Censo Escolar 2026 quanto no ciclo real do SAEB/IDEB 2021. Também confirmou, em nota oficial do MEC/INEP, que o cálculo do IDEB 2021 **não mudou de metodologia** (mesma fórmula desde 2007), mas que o próprio INEP alertou publicamente para cautela na leitura da série por causa de aprovação atípica na pandemia — evidência direta de um viés de "ruptura de série histórica por fator externo" sem mudança formal de metodologia. Ficaram parcialmente não resolvidas: o texto integral da nota técnica do IBGE sobre autodeclaração/proxy na PNAD (bloqueio técnico de acesso ao PDF) e o percentual oficial de adesão de escolas privadas ao SAEB (não publicado como percentual, aparentemente).

## Achados por lacuna da Rodada 1

### 1. Defasagem entre ano de referência e publicação dos microdados

- Cronograma oficial do Censo Escolar 2026 (Portaria INEP nº 219/2026, via reprodução do Conviva Educação): coleta de dados de referência ocorre entre **27/maio e 31/julho/2026**; resultados finais/sinopses estatísticas são previstos para **1º/fevereiro/2027**; indicadores finais de rendimento escolar (2ª etapa, "Situação do Aluno") só saem em **14/maio/2027**. Isso implica defasagem de **~10 meses** entre o fim da coleta e a publicação definitiva dos indicadores de rendimento, e de quase **9 meses** entre o início do ano letivo de referência e a divulgação das sinopses.
- Episódio real e documentado (não hipotético) do ciclo 2021: o MEC/INEP divulgaram os resultados do SAEB e do IDEB 2021 apenas em **16/setembro/2022**, com previsão de liberação dos microdados **"até dezembro de 2022"** — ou seja, quase **12 meses** de defasagem entre o fim do ano de referência (2021) e a disponibilização dos microdados.
- Conclusão: a defasagem de 9–12 meses entre ano de referência e publicação definitiva não é um evento isolado do biênio 2023/2024 (achado da Rodada 1), mas um padrão estrutural recorrente do ciclo INEP (Censo Escolar e SAEB/IDEB), confirmado em pelo menos dois ciclos distintos (2021 e 2026).

### 2. Autodeclaração na PNAD Contínua Educação (nota técnica do IBGE)

- Confirmou-se a existência de nota técnica oficial do IBGE especificamente sobre o módulo de Educação: **"Nota técnica 02/2022 (jul./2022, atualizada em 15/08/2022) — Sobre o módulo anual de Educação em 2020 e 2021"**, hospedada em `ibge.gov.br/novo-portal-destaques/34430-notas-tecnicas-pnad-continua-educacao-em-2020-e-2021`.
- **Não foi possível extrair o conteúdo textual** dessa nota nesta rodada: a página retornou erro 403 ao WebFetch, e o PDF alternativo testado (`liv101959.pdf` da biblioteca IBGE) veio como binário não legível pela ferramenta (aparentemente um artefato de conversão, não o texto da nota). Isso significa que a lacuna sobre vieses específicos de autodeclaração/resposta por proxy na PNAD **permanece em aberto** — é uma lacuna técnica de acesso, não de inexistência da fonte.

### 3. Mudança de metodologia/escala do SAEB ao longo das edições

- Fonte primária identificada (INEP, "Escalas de Proficiência do SAEB", PDF em `download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/escalas_de_proficiencia_do_saeb.pdf`) não pôde ser lida diretamente (falha de certificado SSL na ferramenta de fetch), mas o conteúdo indexado por busca aponta que: a metodologia de escala do SAEB incorporou a Teoria de Resposta ao Item (TRI) em **1995** e a aplicação de Matrizes de Referência em **1997**; no questionário do aluno de **2021** foram incluídos itens novos ("Internet TV", "Internet Celular") e alguns itens comuns ao questionário de 2019 mudaram de nível na escala vigente. **Confiança média** (conteúdo obtido via síntese de busca sobre PDF primário, não leitura direta do texto integral).
- Fonte primária MEC/INEP sobre o ciclo 2021 (lida diretamente, alta confiança): **"O cálculo do indicador de 2021 segue a mesma metodologia proposta em 2007. Entretanto, a pandemia é um fator imprescindível às interpretações."** Isso confirma que, ao menos para o IDEB, **não houve mudança formal de metodologia/escala entre 2007 e 2021** — o que houve foi uma ruptura de comparabilidade por fator externo (pandemia/aprovação atípica), não por redesenho do indicador.
- Conclusão combinada: há evidência de ajustes pontuais em nível de item/questionário (2021) mas não de uma mudança de escala/metodologia central do IDEB desde sua concepção em 2007; a quebra de comparabilidade mais documentada é a de 2021, por causa externa (pandemia), não por mudança de régua.

### 4. Percentual de escolas privadas que aderem ao SAEB

- Confirmado (fonte INEP, via busca): a participação no SAEB é **obrigatória para escolas públicas** e **facultativa para escolas privadas**; escolas privadas passam por uma segunda etapa de adesão via assinatura de "Termo de Adesão" em sistema on-line, com **recolhimento de valor fixado que varia conforme o número de alunos matriculados**.
- A página oficial de perguntas frequentes do INEP sobre o SAEB (lida diretamente) **não publica** nenhum percentual ou número absoluto de escolas privadas participantes em relação ao total elegível, nem valores de taxa, nem se a avaliação é censitária ou amostral por dependência administrativa.
- Conclusão: **a lacuna permanece não fechada** — não há, nas fontes primárias acessadas nesta rodada, um percentual oficial e quantificado de adesão de escolas privadas ao SAEB por edição. O valor citado na Rodada 1 (R$400–R$4.000, via fonte secundária de 2017) não pôde ser confirmado ou refutado nesta rodada por fonte primária (a página original do artigo INEP 2017 está em domínio que não resolve mais — `inep.gov.br` antigo, ENOTFOUND).

### 5. Achados adicionais relevantes (pistas seguidas)

- **Taxas de aprovação por rede/etapa, ciclo 2021 (fonte primária MEC/INEP, alta confiança)**: no ensino fundamental da rede pública, aprovação foi de 91,7% (2019) → 98,4% (2020) → 96,3% (2021); no ensino médio público, 84,7% (2019) → 94,4% (2020) → 89,8% (2021). O MEC/INEP atribui esse salto a "ajustes nos critérios de aprovação e a adoção do continuum curricular" — 72,3% das escolas reorganizaram currículos e 17,2% adotaram "continuum curricular" como estratégias de mitigação da pandemia. Isso é evidência direta e quantificada de como taxas de rendimento podem ser infladas por decisão administrativa/pedagógica sem refletir aprendizagem real — um viés relevante para não superestimar "aprovação" como proxy de baixo risco em anos atípicos.
- **Concepção do IDEB (Nota Técnica nº 1, INEP, via síntese de busca — confiança média)**: IDEB = Proficiência × Fluxo; por ser um índice de dois termos, "não revela por que o fluxo é alto (se por trajetória pedagógica sólida ou por medidas administrativas), nem informa se a aprendizagem está distribuída equitativamente ou concentrada em certos grupos". Isso corrobora textualmente, em fonte oficial, o viés de agregação mencionado na pergunta original (IDEB pode mascarar frequência bruta/variância individual).
- **Distorção idade-série** (fonte INEP, via síntese de busca — confiança média): definida como percentual de alunos com idade acima da recomendada para a série/ano, indicando atraso escolar; é tratada pelo INEP como indicador educacional separado do IDEB, com página própria de dados abertos, mais direto para calibrar "atraso" do que o IDEB composto.

## Limitações desta rodada (metodológicas, da própria pesquisa)

- Vários PDFs primários do INEP hospedados em `download.inep.gov.br` **falharam por erro de certificado SSL** na ferramenta de fetch usada (não é evidência de que a fonte não exista ou esteja errada — é uma limitação de acesso desta sessão). Isso afetou: nota técnica de taxas de transição 2007–2016, nota técnica de concepção do IDEB, e escalas de proficiência do SAEB. Nesses três casos, o conteúdo relatado vem da síntese que a ferramenta de busca (WebSearch) fez sobre os PDFs indexados, não de uma leitura direta e integral — por isso marcados como confiança média, não alta.
- O domínio antigo `inep.gov.br` (sem `www.` nem `gov.br`) não resolve mais (ENOTFOUND) — artigos históricos do INEP hospedados nesse domínio (ex.: adesão de escolas privadas ao SAEB 2017) estão inacessíveis diretamente nesta sessão.
- A nota técnica do IBGE sobre autodeclaração na PNAD Educação não pôde ser lida (403 na página HTML; PDF alternativo veio ilegível). Recomenda-se, numa próxima rodada, localizar o PDF exato da "Nota técnica 02/2022" (não apenas a página de destaque) e tentar acesso via outro caminho (ex.: FTP do IBGE, como funcionou para a nota técnica de rendimentos do trabalho).

## Lacunas remanescentes (para Rodada 3, se houver)

1. Percentual oficial e quantificado de escolas privadas que aderem ao SAEB por edição (não encontrado nesta rodada; a fonte primária de 2017 está em domínio morto).
2. Texto integral da Nota técnica 02/2022 do IBGE sobre autodeclaração/proxy na PNAD Educação (localizada mas não lida — bloqueio técnico de acesso).
3. Confirmação por fonte primária de que o SAEB nunca mudou formalmente sua escala/metodologia de proficiência desde 1997 (a evidência encontrada é indireta, via síntese de busca sobre o PDF de escalas, não leitura direta).
4. Sinopses Estatísticas da Educação Básica (INEP) como fonte tabular granular de taxas de rendimento por rede/etapa/UF — ainda não consultada diretamente nesta rodada (ficou nas pistas da Rodada 1, não priorizada aqui em favor das quatro lacunas centrais).

## Fontes consultadas nesta rodada

| Publisher | Título | Data | URL |
|---|---|---|---|
| Conviva Educação (reproduzindo Portaria INEP nº 219/2026) | Inep divulga cronograma do Censo Escolar da Educação Básica 2026 | 2026 | https://convivaeducacao.org.br/fique_atento/6106 |
| MEC / INEP | MEC e Inep divulgam resultados do Saeb e do Ideb 2021 | 2022-09-16 | https://www.gov.br/mec/pt-br/assuntos/noticias/2022/mec-e-inep-divulgam-resultados-do-saeb-e-do-ideb-2021 |
| INEP | Perguntas frequentes — Sistema de Avaliação da Educação Básica (Saeb) | s.d. | https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/sistema-de-avaliacao-da-educacao-basica-saeb |
| IBGE | Notas técnicas - PNAD Contínua: Educação em 2020 e 2021 | 2022 | https://www.ibge.gov.br/novo-portal-destaques/34430-notas-tecnicas-pnad-continua-educacao-em-2020-e-2021 |
| IBGE (biblioteca) | PNAD Contínua Educação (publicação, PDF não legível nesta sessão) | s.d. | https://biblioteca.ibge.gov.br/visualizacao/livros/liv101959.pdf |
| INEP | Nota Técnica nº 1 — Concepção do IDEB (indexado; não lido diretamente) | s.d. | https://download.inep.gov.br/educacao_basica/portal_ideb/o_que_e_o_ideb/Nota_Tecnica_n1_concepcaoIDEB.pdf |
| INEP | Escalas de Proficiência do SAEB (indexado; não lido diretamente) | s.d. | https://download.inep.gov.br/publicacoes/institucionais/avaliacoes_e_exames_da_educacao_basica/escalas_de_proficiencia_do_saeb.pdf |
| INEP | Nota técnica — Taxas de Transição 2007-2016 (indexado; falha de leitura) | s.d. | https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/2007_2016/nota_tecnica_taxas_transicao_2007_2016.pdf |
| INEP (artigo, domínio antigo — inacessível) | Adesão das escolas privadas ao Saeb 2017 começa nesta terça-feira, 27 | 2017 | http://inep.gov.br/artigo/-/asset_publisher/B4AQV9zFY7Bv/content/adesao-das-escolas-privadas-ao-saeb-2017-comeca-nesta-terca-feira-27/21206 |

## Pistas para próxima rodada

- Buscar o PDF direto da Nota técnica 02/2022 do IBGE (não a página de destaque) — tentar via `ftp.ibge.gov.br` (caminho que funcionou para a nota técnica de rendimentos do trabalho nesta mesma busca).
- Buscar a versão em cache/arquivo (Wayback Machine) do artigo INEP 2017 sobre adesão de escolas privadas, já que o domínio original não resolve mais.
- Tentar acessar os PDFs de `download.inep.gov.br` por outro método (ex.: mirror, Google Cache, ou ferramenta de fetch diferente), já que o certificado SSL bloqueou o acesso direto nesta sessão a pelo menos três notas técnicas centrais (IDEB, taxas de transição, escalas de proficiência do SAEB).
- Sinopses Estatísticas da Educação Básica (INEP) — ainda não consultadas como fonte tabular granular.
- Artigo Redalyc "O algoritmo do Ideb e as metas projetadas para a Educação brasileira: uma análise estatístico-matemática" (apareceu de novo nesta rodada) — ler na íntegra para os limites estatístico-matemáticos do IDEB, indicado desde a Rodada 1 e ainda não lido.
