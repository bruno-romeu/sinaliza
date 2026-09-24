# Distribuições reais — Rodada 2 (aprofundamento)

**Data da pesquisa:** 2026-09-17
**Objetivo:** Fechar lacunas da Rodada 1 sobre distribuições reais de frequência, notas, evasão/abandono e atividades não entregues no Brasil (educação básica), para calibrar gerador de dataset sintético.

---

## 1. Reconciliação parcial: "abandono" 3,4%–3,9% vs "evasão" 5,9% (Ensino Médio, 2023)

A discrepância da Rodada 1 **foi parcialmente esclarecida** (não totalmente reconciliada com tabela primária, mas com base conceitual sólida):

- O **Dicionário de Indicadores Educacionais do INEP** (achado via busca, PDF não acessível diretamente por erro de certificado) distingue explicitamente:
  - **Abandono**: situação do aluno apurada pelo Censo Escolar ao final do ano letivo — três condições possíveis (aprovado, reprovado, abandono). É um indicador de "situação final" dentro do mesmo ano letivo.
  - **Evasão**: conceito diferente, calculado via "taxas de transição" — compara a matrícula de um aluno em um ano com sua situação (ou ausência) no ano seguinte. Um aluno reprovado que não volta a se matricular conta como evasão, mesmo sem ter sido classificado como "abandono" no ano anterior.
  - Fonte: página institucional INEP + Undime, que descrevem o Dicionário (PDF original bloqueado por erro de certificado, mesmo problema da Rodada 1).
- Isso é consistente com os números da **QEdu Conteúdos** para 2019/2020 (Ensino Médio): abandono (fim de ano) = **4,7%**; evasão (transição, ano seguinte) = **6,9%** — evasão sistematicamente maior que abandono, confirmando que são métricas diferentes, não uma contradição de dados.
- Para o Censo Escolar 2023, um resultado de busca (Agência Gov, fev/2024, citando coletiva de imprensa do MEC/INEP) aponta Ensino Médio como etapa com maior taxa de **repetência (reprovação) 3,9%** e **evasão 5,9%** — não foi possível abrir a página diretamente (bloqueada por "indisponibilidade temporária por legislação eleitoral"), então este número vem do resumo de busca, não da tabela primária.
- **Conclusão de trabalho (confiança média)**: o "3,4%" da Rodada 1 provavelmente se referia a "abandono" (indicador de situação final, ano corrente) e o "5,9%" a "evasão" (indicador de transição/não-retorno) — são categorias INEP oficialmente distintas, então ambos os números podem estar corretos simultaneamente, referindo-se a coisas diferentes. Isso **não foi verificado lendo a tabela primária linha a linha** — continua sendo uma lacuna para quem precisar do valor exato oficial.

## 2. Taxas de insucesso escolar (reprovação + abandono) por série crítica — dado novo relevante

Fonte: Fundação Carlos Chagas, notícia sobre Censo Escolar 2023 (lida com sucesso via WebFetch).

Estas são as **séries historicamente mais críticas** no Brasil (3º e 6º ano do Ensino Fundamental, 1º ano do Ensino Médio), com taxa combinada de reprovação + abandono ("insucesso escolar"):

| Série | 2019 (pré-pandemia) | 2020 (início ERE) | 2022 (retomada presencial) |
|---|---|---|---|
| 3º ano EF | 10,2% | 1,3%* | 6,8% |
| 6º ano EF | 13,8% | 2,4%* | 8,7% |
| 1º ano EM | 21,3% | 6,4%* | 16,4% |

\* Os valores de 2020 refletem promoção quase automática durante o ensino remoto emergencial (ERE), não uma melhora real de aprendizagem — usar com cautela para calibração, é um outlier pandêmico.

Isso é um dado importante de calibração: **1º ano do Ensino Médio pode ter taxa de insucesso escolar de ~16-21% em anos "normais"**, muito acima da média geral da rede, e útil para modelar um subgrupo de "alunos em risco" mais concentrado nessa série de transição.

Dados adicionais de evasão por perfil (Censo Escolar 2023, mesma fonte):
- Evasão masculino: 3,5% / feminino: 2,6%
- Evasão brancos: 2,1% / pretos e pardos: 3,5%

(Não fica claro no resumo se esses % de evasão por gênero/raça são específicos do Ensino Médio ou da educação básica agregada — tratar com confiança média.)

## 3. Censo Escolar 2024 — já publicado (mais atual que 2023)

Confirmado: o Censo Escolar da Educação Básica 2024 **já teve resultados divulgados em 9 de abril de 2025** (primeira etapa, matrícula/infraestrutura), pelo MEC/INEP.

Dados extraídos (fonte: cobertura oficial MEC/INEP, buscas em radiogov.ebc.com.br, gov.br/mec, gov.br/inep):
- 47,1 milhões de matrículas em 179,3 mil escolas de educação básica em 2024 — queda de 0,46% (~215 mil matrículas a menos) frente a 2023.
- Rede pública perdeu 310 mil matrículas; rede privada ganhou 94 mil matrículas no mesmo período.
- 2,4 milhões de professores; 163.987 diretores (91,5% com formação superior; 80,6% mulheres).
- Acesso à internet na rede pública: 88,5% (2023) → 90,0% (2024).
- Educação profissional e tecnológica (rede pública): crescimento de 17% frente a 2023, totalizando 1.570.993 matrículas.

**Não foi possível**, dentro do orçamento desta rodada, obter as taxas de rendimento (aprovação/reprovação/abandono) específicas do Censo 2024 — os PDFs primários (`notas_estatisticas_censo_da_educacao_basica_2024.pdf`, `apresentacao_coletiva.pdf`) retornaram o mesmo erro de certificado da Rodada 1 ao tentar acesso direto via WebFetch.

## 4. SAEB 2023 — estrutura de distribuição confirmada, números agregados não extraídos

Fonte: resumos de busca apontando para o Relatório SAEB 2023 Volume 1 (INEP) e cobertura do Movimento pela Base (PDF original não acessado por erro de certificado).

- Confirma-se que o relatório SAEB 2023 **traz médias nacionais e estaduais acompanhadas da distribuição de estudantes na escala de proficiência**, por área de conhecimento — ou seja, existe uma distribuição pública, mas em **escala de proficiência (pontos), não em escala 0-10**. Isso reforça o gap da Rodada 1: não existe conversão oficial SAEB → nota 0-10.
- Estrutura de 4 níveis de proficiência confirmada (via QEdu/plataformas que replicam o SAEB): **insuficiente, básico, proficiente, avançado** — mas os percentuais de alunos em cada nível para 2023 não foram extraídos nesta rodada (PDF bloqueado).
- Após queda de "cerca de meio desvio-padrão" entre 2019 e 2021 (efeito pandemia), o desempenho em 2023 voltou a ficar "muito mais próximo" do nível de 2019, segundo resumo do Movimento pela Base — indica recuperação parcial pós-pandemia, mas sem number exato de quanto.
- Achado colateral (não é distribuição de notas, mas é dado numérico real): o **INSE (Indicador de Nível Socioeconômico) do SAEB 2023** tem média nacional de **5,10** e desvio-padrão de **0,97** (nota técnica INEP, via resumo de busca — não é proficiência de aluno, é nível socioeconômico da escola/aluno, útil apenas como proxy indireto de contexto, não de nota).

## 5. Frequência/assiduidade diária — sem avanço

Não foi encontrada nesta rodada nenhuma fonte pública nova com frequência diária/cotidiana em sala de aula (percentual de presença por aula/dia). Continua valendo o achado da Rodada 1: a única frequência oficial disponível é a "frequência líquida ajustada" da PNAD Contínua (proporção da população em determinada faixa etária frequentando a etapa educacional adequada), que é um conceito de adequação idade-série, não de assiduidade diária.

## 6. Atividades/tarefas não entregues — sem avanço

Nenhuma fonte pública foi localizada nesta rodada (nem em buscas nem nas pistas seguidas) com dado agregado ou por aluno sobre entrega/não entrega de tarefas ou atividades escolares. Este continua sendo um item para o qual **não existe referência estatística pública brasileira** — qualquer taxa usada no gerador sintético para esta variável precisa ser tratada como suposição de design, não calibrada por dado real.

## 7. QEdu e PDFs oficiais INEP — acesso ainda bloqueado

- `qedu.org.br/brasil/taxas-rendimento` retornou **HTTP 403** novamente nesta rodada (mesmo bloqueio da Rodada 1).
- Todos os PDFs sob `download.inep.gov.br` tentados (dicionário de indicadores, notas estatísticas do censo 2024, resumo técnico 2023, relatório SAEB 2023) retornaram **"unable to verify the first certificate"** — problema de certificado SSL do domínio, não de conteúdo. Isso bloqueia leitura direta de qualquer PDF primário do INEP neste ambiente de pesquisa.
- Em compensação, a subseção `conteudos.qedu.org.br` (blog de conteúdo, subdomínio diferente da aplicação principal) **foi acessível** e forneceu dados reais com citação de fonte primária (Censo Escolar, categoria "taxas de transição").
- Painéis interativos do Observatório de Educação do Instituto Unibanco (`observatoriodeeducacao.institutounibanco.org.br`) são renderizados via JavaScript — o WebFetch só recupera metadados da página (ex.: "dado mais recente: 2022"), não os valores numéricos das visualizações.

## Recomendação prática para calibração do gerador sintético

Com os dados disponíveis (Rodada 1 + Rodada 2), a base mais sólida para calibrar o gerador é:
- **Evasão/abandono**: usar abandono ~3-5% e evasão ~5-7% como faixas gerais no Ensino Médio (mais alto, ~16-21% de insucesso combinado no 1º ano EM especificamente); Ensino Fundamental anos finais mais baixo, com pico no 6º ano (~8-14% dependendo do ano).
- **Notas 0-10**: não há distribuição oficial nessa escala — é necessário assumir uma distribuição sintética razoável (ex.: normal truncada centrada em 6-7) e documentar isso como suposição de design, não como dado calibrado.
- **Frequência diária**: idem — não há dado oficial; usar suposição de design.
- **Atividades não entregues**: idem — sem dado público, suposição de design.

---

## Claims com fonte (ver também objeto estruturado retornado)

Ver lista `claims` no retorno estruturado desta tarefa para o detalhamento com URL, publisher, data e nível de confiança de cada afirmação acima.

## Fontes consultadas nesta rodada

Ver lista `sources` no retorno estruturado.

## Gaps remanescentes

Ver lista `gaps` no retorno estruturado.

## Pistas para Rodada 3 (se houver)

Ver lista `leads` no retorno estruturado.
