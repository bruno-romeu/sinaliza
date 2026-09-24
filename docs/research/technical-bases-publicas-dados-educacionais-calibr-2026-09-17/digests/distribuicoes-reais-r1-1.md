# Digest — Distribuições reais (frequência, notas, evasão, atividades não entregues)

**Rodada:** r1 · **Data:** 2026-09-17 · **Escopo:** bases públicas de dados educacionais no Brasil (educação básica), para calibrar gerador de dataset sintético de ~200 alunos fictícios (sistema de detecção precoce de risco escolar).

**Regra de epistemologia aplicada:** toda afirmação abaixo tem fonte pesquisada nesta rodada (busca/leitura via WebSearch/WebFetch). Conhecimento prévio não entrou como conclusão — apenas guiou as buscas. Números conflitantes entre fontes são reportados como tal, não resolvidos por julgamento.

---

## 1. Taxa de frequência/assiduidade escolar

- **Ensino Fundamental (6–14 anos):** frequência escolar praticamente universal, entre 98,9% e 100% conforme faixa etária, segundo a PNAD Contínua (IBGE). *(confiança: média — dado veio de um resumo agregado de busca, não de leitura direta da tabela do IBGE)*
- **Ensino Médio (15–17 anos):** taxa de frequência líquida ajustada nacional de **80,6%**, PNAD Contínua Educação. Esse indicador mede o % de jovens de 15–17 anos frequentando a etapa esperada para a idade (não é frequência diária/assiduidade em sala) — atenção para não confundir com "taxa de presença em aula", que não tem publicação nacional equivalente.
- **Não encontrado:** uma métrica pública nacional de "frequência diária média" ou "% de faltas por aluno/ano" — o Censo Escolar/INEP não publica isso agregado; a frequência que aparece nos indicadores oficiais é a **frequência líquida ajustada** (proxy de acesso/permanência na idade certa), não assiduidade cotidiana. Isso é uma lacuna relevante para quem quer calibrar "taxa de presença em aula".

## 2. Distribuição de notas escolares (escala 0–10)

- **Não existe base pública nacional de distribuição de notas de boletim (escala 0–10)** por rede/região. O Censo Escolar e o INEP não coletam nem publicam notas bimestrais/anuais dos alunos — apenas resultado final (aprovado/reprovado/abandono), que é outra variável.
- A prática de nota mínima para aprovação de 6,0 ou 7,0 é comum nas redes, mas é definida por regimento de cada rede/escola, não há tabela nacional consolidada.
- O que existe publicamente é a **proficiência do SAEB** (escala de 0 a ~1000 pontos, não 0–10) — não conversível de forma direta ou oficial para notas de boletim. Dado de 2023: no último ano da educação básica, **59% dos estudantes estão no nível "Insuficiente" em Matemática** (INEP/SAEB, distribuição em 4 níveis: Insuficiente, Básico, Proficiente, Avançado — usada pelo QEdu). No 2º ano do Ensino Fundamental, **49% dos alunos da rede pública estão alfabetizados, contra 77% na rede privada** (SAEB 2023).
- Proficiência média por estado (escala SAEB): menores médias em Tocantins (718,8), Pará (719,0), Amapá (720,8); Santa Catarina com 757,4 (2ª maior do país). Fonte: relatório SAEB 2023 (INEP), via cobertura secundária.
- **Conclusão para calibração:** não há como calibrar uma distribuição real de notas 0–10 com fonte pública direta; a alternativa mais próxima e rastreável é usar a distribuição de níveis de proficiência do SAEB como proxy de desempenho (4 categorias), documentando essa aproximação como decisão de modelagem.

## 3. Taxa de evasão/abandono e reprovação escolar (Censo Escolar/INEP)

Atenção: **"taxa de abandono" (indicador oficial INEP, calculado por rendimento escolar dentro do ano) é diferente de "taxa de evasão"** (métrica mais ampla, usada por alguns agregadores/imprensa, que considera não-retorno no ano seguinte). Os números abaixo por vezes divergem entre si por essa razão — reportados como estão, sem reconciliar.

- **Taxas de abandono, Censo Escolar 2023 (INEP/MEC), consolidado divulgado fev/2024:** 3,0% no Ensino Fundamental e 5,9% no Ensino Médio (nota: uma fonte de imprensa cita isso como "evasão"). No Ensino Médio: 3,8% (masculino) vs. 2,9% (feminino).
- **Série histórica de reprovação (taxas de rendimento, comparação pré/pós-pandemia, INEP/FCC):**
  - 3º ano EF: 10,2% (2019) → 1,3% (2020, pandemia) → 6,8% (2023)
  - 6º ano EF: 13,8% (2019) → 2,4% (2020) → 8,7% (2023)
  - 1º ano EM: 21,3% (2019) → 6,4% (2020) → 16,4% (2023)
  → padrão: reprovação e abandono caíram artificialmente durante a pandemia (promoção automática/remoto) e retomaram crescimento em 2023, aproximando-se (mas ainda abaixo, em EF) dos níveis pré-pandemia.
- **Anos iniciais do EF, comparação 2022→2023 (INEP, taxas de rendimento 2023):** reprovação caiu de 3,5% (2022) para 2,5% (2023); abandono caiu de 0,5% (2022) para 0,3% (2023).
- **Ensino Médio, abandono nacional:** uma fonte cita 3,4% em 2023 (melhoria vs. 5,7% em 2022) — **diverge** do dado de 5,9% citado acima como "evasão" no EM 2023; ambos remetem a fontes ligadas ao INEP/Censo Escolar 2023, mas parecem usar bases/definições distintas (abandono vs. evasão, ou corte temporal diferente). Registrar ambos com baixa confiança até reconciliação.
- **Distribuição por modalidade de ensino, Censo Escolar 2023 (Ensino Fundamental):** maior evasão na educação indígena (7,3%), seguida de educação especial (4,9%) e quilombola (4,8%).
- **Ensino Médio por raça/cor:** pretos e pardos com maior abandono (6,3%) — fonte não detalha o comparativo com brancos nesse recorte específico.
- **Matrículas por rede no Ensino Médio (2023):** rede estadual concentra 83,6% das matrículas (6,4 milhões de alunos); rede privada, 12,8% (≈986,3 mil alunos).
- **Distorção idade-série (Censo Escolar 2023, INEP):** 4,28 milhões de estudantes em distorção idade-série no Brasil. Por região: Nordeste 35,9% (1,54 milhão), Sudeste 27,8% (1,19 milhão), Norte 17,1% (733,9 mil) do total nacional de alunos em distorção. Nos anos finais do EF, distorção de pretos/pardos (20,9%) é quase o dobro da de alunos brancos (10,8%).
- **IDEB 2023 (INEP, sem metas estipuladas nesta edição, mas comparável a 2019):**
  - Anos iniciais EF (rede pública): IDEB 5,7 (igual a 2019); indicador de aprendizagem caiu de 6,02→5,91; indicador de fluxo subiu de 0,94→0,97.
  - Anos finais EF (rede pública): IDEB 4,7 (2023) vs. 4,6 (2019); aprendizagem 5,21→5,10; fluxo 0,89→0,93.
  - Ensino Médio (rede estadual): IDEB 4,1 (2023) vs. 3,9 (2019); aprendizagem 4,54→4,45; fluxo 0,85→0,92.
  - Apenas 8 estados melhoraram o indicador de aprendizagem no EM; nos anos iniciais, só 6 estados melhoraram (destaques: Alagoas, Maranhão, Ceará).
- **Conclusão de etapas (Todos Pela Educação, análise 2015–2025, sem indicação de fonte primária direta no que foi lido):** taxa de conclusão do Ensino Fundamental até os 16 anos em 88,6%; conclusão do Ensino Médio até os 19 anos em 74,3%. *(confiança média — não li o documento primário completo, apenas resumo de busca)*.

## 4. Taxa de atividades/tarefas não entregues

- **Gap confirmado:** não existe indicador público no Censo Escolar, INEP, IDEB ou SAEB sobre "% de atividades/tarefas não entregues" por aluno. Esse tipo de dado é operacional/interno de plataformas de gestão escolar (SEDs estaduais, sistemas de LMS) e não é consolidado nem publicado nacionalmente. Buscas dedicadas a esse ponto não retornaram nenhuma base de dados abertos ou estudo com esse indicador — apenas confirmam que os indicadores públicos disponíveis são aprovação/reprovação/abandono (rendimento) e frequência líquida ajustada, não entrega de tarefas.
- Recomendação para o gerador sintético: tratar "taxa de atividades não entregues" como uma variável sem calibração por fonte pública direta — se necessário, ancorar indiretamente à taxa de reprovação/abandono (que tem fonte) como proxy de risco, documentando a ausência de dado primário para essa variável específica.

---

## Lacunas (gaps)

1. Nenhuma fonte pública com distribuição de notas de boletim em escala 0–10 (nacional, por rede ou região).
2. Nenhum indicador público de "frequência diária"/assiduidade cotidiana (só frequência líquida ajustada por idade/etapa, PNAD Contínua).
3. Nenhum dado público sobre "atividades/tarefas escolares não entregues".
4. Discrepância não resolvida entre "taxa de abandono" (3,4%–5,9%, dependendo da fonte) para o Ensino Médio em 2023 — não consegui, dentro do orçamento desta rodada, acessar a tabela primária do INEP (PDFs oficiais deram erro de certificado/acesso na ferramenta de fetch) para reconciliar definições.
5. Não consegui abrir diretamente os PDFs oficiais do INEP (`taxas_de_rendimento_escolar_2023.pdf`, `resumo_tecnico_censo_escolar_2023.pdf`) nem o portal QEdu (bloqueio de acesso/certificado) — os números vêm de resumos de busca que citam esses documentos como fonte primária, não de leitura direta linha a linha. Recomendo tentar de novo com download direto (não fetch com verificação de certificado) numa próxima rodada.
6. Não busquei especificamente por Censo Escolar 2024 (mais recente que 2023) — os números aqui são todos de referência 2023 ou anteriores; pode haver dado mais novo já publicado.

## Leads para próxima rodada

- **QEdu (qedu.org.br)** — portal que consolida taxas de rendimento por escola/rede/região a partir do Censo Escolar; bloqueou fetch direto (403) nesta rodada, mas é a fonte mais granular para aprovação/reprovação/abandono por dependência administrativa. Vale tentar acesso via outro método.
- **INEP — Dicionário de Indicadores Educacionais** (`download.inep.gov.br/publicacoes/institucionais/estatisticas_e_indicadores/dicionario_de_indicadores_educacionais_formulas_de_calculo.pdf`) — define fórmulas exatas de cada taxa (abandono, evasão, distorção), útil para não confundir métricas na calibração.
- **Portal de Dados Abertos do INEP** (`dados.gov.br/dataset/inep-indicador-educacional-da-educacao-basica-taxas-de-rendimento-escolar`) — dataset bruto de taxas de rendimento, permitiria extrair microdados por UF/rede/etapa em vez de depender de resumos de imprensa.
- **SAEB 2023 — relatório completo** (`download.inep.gov.br/saeb/resultados/relatorio-saeb_volume_1_2023.pdf`) — não lido diretamente; teria a distribuição completa por níveis de proficiência e desvio-padrão, útil como proxy de "distribuição de notas".
- **Observatório de Educação (Instituto Unibanco)** — publica série histórica de taxa de abandono no EM por faixa etária; pode ajudar a reconciliar a discrepância 3,4% vs 5,9%.
- **Todos Pela Educação — "Conclusão da Educação Básica: avanços e desigualdades da última década" (2025)** — documento extenso sobre taxas de conclusão por renda/raça/sexo; não lido no detalhe, só resumo de busca.
- **Censo Escolar 2024** (já deve ter sido divulgado, dado que hoje é set/2026) — dado mais recente que os aqui reportados (todos de 2023).
- **PNAD Contínua Educação (IBGE)**, publicação anual — para taxa de frequência líquida por idade, com série histórica e desagregação por renda/raça/região; só acessei resumo, não a tabela.

---

## Fontes consultadas nesta rodada

| Publisher | Título | Data | URL |
|---|---|---|---|
| FCC (Fundação Carlos Chagas) | Censo Escolar 2023: reprovação e abandono escolar retomam crescimento após pandemia | 2024 | https://www.fcc.org.br/fcc-noticia/censo-escolar-2023-reprovacao-e-abandono-retomam-crescimento-apos-pandemia/ |
| isaac.com.br (blog, secundário) | Evasão escolar na educação básica atinge a taxa de 5,9% em 2023 | 2024 | https://isaac.com.br/blog/censo-escolar-evasao-escolar-educacao-basica |
| Agência Gov (EBC) | Ensino médio tem maior taxa de evasão da educação básica | 2024-02 | https://agenciagov.ebc.com.br/noticias/202402/ensino-medio-tem-maior-taxa-de-evasao-da-educacao-basica |
| INEP (portal.inep.gov.br) | Confira as taxas de aprovação, reprovação e abandono escolar | s/d | http://portal.inep.gov.br/artigo/-/asset_publisher/B4AQV9zFY7Bv/content/confira-as-taxas-de-aprovacao-reprovacao-e-abandono-escolar/21206 |
| INEP | Taxas de Distorção Idade-série (dados abertos) | 2023 | https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-distorcao-idade-serie |
| Blog do IBRE (FGV) | Os avanços na redução da distorção idade-série: Ceará é o destaque | 2023/2024 | https://blogdoibre.fgv.br/posts/os-avancos-na-reducao-da-distorcao-idade-serie-ceara-e-o-destaque |
| INEP | Relatório SAEB 2023, Volume 1 | 2024 | https://download.inep.gov.br/saeb/resultados/relatorio-saeb_volume_1_2023.pdf |
| QEdu / Iede | QEdu disponibiliza taxas de rendimento 2023 para cada um dos anos escolares | 2024 | https://portaliede.org.br/contribuicao/qedu-disponibiliza-taxas-de-rendimento-2023-para-cada-um-dos-anos-escolares/ |
| QEdu | Brasil: Taxas de Rendimento | 2023/2024 | https://qedu.org.br/brasil/taxas-rendimento |
| INEP | Nota Informativa do IDEB 2023 | 2024 | https://download.inep.gov.br/ideb/nota_informativa_ideb_2023.pdf |
| Todos Pela Educação | Ideb e Saeb: veja os destaques dos resultados de 2023 | 2024 | https://todospelaeducacao.org.br/noticias/ideb-e-saeb-veja-os-destaques-dos-resultados-de-2023/ |
| Exame | Ideb 2023: veja o resultado por estado e região | 2024 | https://exame.com/brasil/ideb-2023-veja-resultado-por-estado-e-regiao/ |
| IBGE | PNAD Contínua Educação 2025 (informativo) | 2025 | https://biblioteca.ibge.gov.br/visualizacao/livros/liv102286_informativo.pdf |
| Correio Braziliense | Taxa de evasão escolar no ensino médio é menor em escolas públicas integrais | 2024-08 | https://www.correiobraziliense.com.br/euestudante/educacao-basica/2024/08/6922290-taxa-de-evasao-escolar-no-ensino-medio-e-menor-em-escolas-publicas-integrais.html |
| Observatório de Educação (Instituto Unibanco) | Histórico da taxa de abandono na rede pública de Ensino Médio por faixa etária | s/d | https://observatoriodeeducacao.institutounibanco.org.br/educacao-em-numeros/visualizacao/historico-da-taxa-de-abandono-na-rede-publica-de-ensino-medio-por-faixa-etaria-dos-estudantes,dd985d05-d94c-4487-a090-27c4af25a6c1 |
| Todos Pela Educação | Conclusão da Educação Básica: avanços e desigualdades da última década | 2025 | https://todospelaeducacao.org.br/wordpress/wp-content/uploads/2025/11/estudo-conclusao-na-educacao-basica-todos-pela-educacao.pdf |
| dados.gov.br (Portal Brasileiro de Dados Abertos) | Inep: Indicador Educacional da Educação Básica — Taxas de Rendimento Escolar | s/d | https://dados.gov.br/dataset/inep-indicador-educacional-da-educacao-basica-taxas-de-rendimento-escolar |

**Não acessados com sucesso (erro técnico), citados apenas indiretamente via resumos de busca:**
- https://download.inep.gov.br/publicacoes/institucionais/estatisticas_e_indicadores/taxas_de_rendimento_escolar_2023.pdf (erro de certificado)
- https://download.inep.gov.br/publicacoes/institucionais/estatisticas_e_indicadores/resumo_tecnico_censo_escolar_2023.pdf (erro de certificado)
- http://portal.inep.gov.br/artigo/.../21206 (connection refused)
- https://qedu.org.br/brasil/taxas-rendimento (HTTP 403)

---

**stop_reason: budget** — o orçamento de ~10 chamadas de busca/leitura foi usado; várias fontes primárias do INEP (PDFs oficiais) não puderam ser abertas por erro técnico da ferramenta de fetch (certificado/bloqueio), o que deixou pontos (sobretudo a reconciliação abandono vs. evasão no EM 2023, e os dados por rede/dependência administrativa) apoiados em resumos de terceiros em vez de leitura direta da tabela primária.
