---
title: 'technical research: Bases públicas de dados educacionais (frequência, notas, evasão) para calibrar distribuições de um gerador de dataset sintético de ~200 alunos'
type: 'technical'
topic: 'Bases públicas de dados educacionais (frequência, notas, evasão) para calibrar distribuições de um gerador de dataset sintético de ~200 alunos'
decision: 'Calibrar as distribuições (taxas de frequência, distribuição de notas, taxas de evasão/queda de desempenho, atividades não entregues) do gerador de dados sintéticos do Sinaliza com base em fontes públicas brasileiras reais, para que o dataset de ~200 alunos fictícios seja estatisticamente plausível.'
source: 'native run'
status: complete
preset: 'standard'
validation: 'normal'
created: '2026-09-17'
updated: '2026-09-17'
claims_verified: 6
claims_unverified: 3
claims_disputed: 1
claims_overturned: 0
---

# technical research: Bases públicas de dados educacionais (frequência, notas, evasão) para calibrar distribuições de um gerador de dataset sintético de ~200 alunos

**Decision this research serves:** Calibrar as distribuições (taxas de frequência, distribuição de notas, taxas de evasão/queda de desempenho, atividades não entregues) do gerador de dados sintéticos do Sinaliza com base em fontes públicas brasileiras reais, para que o dataset de ~200 alunos fictícios seja estatisticamente plausível.

## Resumo executivo

Existem bases públicas brasileiras sólidas para calibrar **evasão/abandono** e **desempenho relativo** (proficiência), mas nenhuma para **notas em escala 0–10**, **frequência diária/assiduidade** ou **atividades não entregues** — essas três variáveis, centrais ao modelo de dados do Sinaliza, não têm equivalente estatístico público no Brasil e precisarão ser tratadas como suposições de design documentadas, não como dado calibrado.

Três achados dominam a decisão:

1. **Só dá para calibrar por escola/rede, nunca por aluno.** Desde o Censo Escolar 2021 (mudança de 2022), o INEP reestruturou os microdados públicos para conformidade com a LGPD — o RIPD oficial do INEP declara textualmente que o novo modelo é "agregado por escola" para o Censo Escolar [3][4][5]. O acesso a dados desagregados por aluno exige projeto de pesquisa aprovado via Sedap [12]. Isso significa que o gerador sintético não pode "amostrar" um aluno real anonimizado do INEP — só pode calibrar contra taxas agregadas (uma escola/rede tem X% de abandono) e depois **desenhar** a distribuição individual por aluno como decisão de modelagem.
2. **As taxas de evasão/abandono têm fonte primária e são a variável mais bem calibrável.** Censo Escolar 2023: abandono ~3,0% (Ensino Fundamental) e evasão ~5,9% / reprovação 3,9% (Ensino Médio) [20][21], confirmados de forma independente por MEC/INEP e Fundação Carlos Chagas. O Ensino Médio concentra o risco, com o **1º ano do EM** chegando a 16–21% de "insucesso escolar" (reprovação + abandono) em anos não atípicos [20].
3. **Notas, frequência diária e atividades não entregues não têm base pública brasileira.** O único proxy de desempenho é a proficiência do SAEB (escala de pontos, 4 níveis categóricos, não 0–10) [23]; o único proxy de frequência é a "frequência líquida ajustada" (adequação idade-etapa, não assiduidade diária) [9]; não existe fonte para "atividades não entregues" em nenhuma base pesquisada.

**Maior ressalva:** boa parte dos números carrega confiança média, não alta — muitos PDFs primários do INEP bloquearam o fetch automatizado por erro de certificado SSL ou "conteúdo restrito", forçando os pesquisadores a citar sínteses de busca em vez de ler a tabela oficial linha a linha. Isso é reportado claim a claim abaixo, e não foi contornável dentro do orçamento deste run.

---

## 1. Bases existentes

As bases públicas brasileiras relevantes cobrem quatro grandes fontes federais e um conjunto de portais estaduais/municipais que, em geral, apenas espelham as federais:

- **Censo Escolar da Educação Básica (INEP)** — o levantamento central: escolas, turmas, matrículas e docentes, anual, cobertura nacional censitária (pública e privada) [1]. É a fonte primária das taxas de rendimento (aprovação/reprovação/abandono) e de distorção idade-série.
- **SAEB — Sistema de Avaliação da Educação Básica (INEP)** — avaliação de proficiência (Língua Portuguesa e Matemática) por amostragem, bienal desde 1990, obrigatória para a rede pública e facultativa (mediante adesão paga) para a rede privada [7][29].
- **IDEB — Índice de Desenvolvimento da Educação Básica (INEP)** — indicador derivado (`Proficiência SAEB × Fluxo do Censo Escolar`), não é uma base de microdados, é consultado via painel por escola/rede/UF [6][16].
- **PNAD Contínua — módulo Educação (IBGE)** — pesquisa amostral domiciliar (não é registro de matrícula), com dado anual de frequência líquida, escolaridade e abandono por faixa etária/renda/raça [9].
- **QEdu** — portal agregador (Fundação Lemann/Meritt) que replica a metodologia oficial do INEP para calcular taxas de rendimento por escola/município/estado; não é fonte primária, mas é o caminho mais acessível para consultar números já calculados [8][22].
- **Portais estaduais/municipais de dados abertos** (SP, RJ, MG identificados) — o único testado em detalhe (São Paulo) mostrou ser um espelho do INEP, sem granularidade adicional e "Nenhuma Licença Fornecida" no catálogo [11][19]; os demais portais foram localizados mas seus datasets de educação não foram abertos/inspecionados neste run — permanecem como pista, não como fato confirmado.
- **Busca Ativa Escolar (UNICEF/Undime/Congemas/Conasems)** — ferramenta operacional de monitoramento de frequência e evasão usada por municípios, não uma base pública nacional de microdados consultável; útil só como referência de quais variáveis municípios já monitoram na prática (frequência em tempo real, motivo de evasão) [33].

Nenhuma base encontrada mede "atividades/tarefas não entregues" — recorrente em todas as quatro dimensões pesquisadas (ver Seção 4 e Perguntas em aberto).

As "taxas de rendimento" (aprovação/reprovação/abandono) citadas ao longo deste relatório seguem uma metodologia oficial fixada pelo INEP desde 2010 e mantida sem alteração relevante desde então [13].

## 2. Acesso e formato

- **Licença:** o rodapé institucional do site do INEP declara Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada (CC BY-ND 3.0) [1][7] — mas não há confirmação de que essa é a licença específica dos pacotes de microdados em si (pode ser só a licença editorial do portal); tratar com confiança média.
- **Formato:** os pacotes de microdados do INEP (Censo Escolar, SAEB, ENEM) são distribuídos como arquivos comprimidos com dados tabulares (CSV/ASCII, delimitador ainda não confirmado com certeza — pipe no Censo Escolar/ENEM segundo fontes secundárias, vírgula no SAEB), dicionário de dados, "Leia-Me" e programas de leitura para SAS/SPSS/R [1][7][14]. O RIPD do ENEM (fonte primária lida integralmente) confirma isso para o ENEM 2021: CSV, 3.389.832 registros, 1,4 GB, 76 campos por registro [14].
- **LGPD e anonimização — o achado mais importante desta dimensão.** O RIPD dos Censos da Educação (INEP, 30/12/2022, fonte primária lida integralmente) [3] declara que o INEP "estruturou um novo modelo de arquivos de microdados públicos **agregados por escola**" para o Censo Escolar, como técnica de controle de divulgação estatística — reduzindo deliberadamente o volume de informação disponível para baixar o risco de reidentificação de "elevado" para "médio"/"baixo" [3]. Essa mudança foi confirmada de forma independente por reportagem do Correio Braziliense de fevereiro de 2022 ("Inep remove microdados do Censo Escolar e do Enem e oculta informações") [4], pela nota oficial de esclarecimento do INEP [5] e por cobertura contemporânea do mesmo episódio [2]. O INEP cita conformidade com a Lei 13.709/2018 (LGPD) e parceria técnica com o Laboratório Inscrypt (UFMG) para os critérios de divulgação. O processo foi acompanhado por uma fiscalização formal da ANPD [17]; uma nota técnica de terceiros detalha quais variáveis de identificação de aluno deixaram de constar nas bases públicas a partir de 2019 [18]. **Status: verificado** (duas fontes independentes — INEP primário + Correio Braziliense — mais a nota oficial do INEP corroborando).
  - Existe uma tensão não resolvida nos próprios digests desta pesquisa: o mesmo RIPD também é compatível, em outras passagens, com a manutenção de arquivos "ALUNOS" com registro por aluno mas variáveis identificadoras suprimidas (modelo análogo ao ENEM, onde o formato de registro por pessoa foi preservado e apenas campos como CO_ESCOLA, idade exata e naturalidade foram suprimidos/generalizados) [3][14]. Nenhum documento lido neste run resolve definitivamente se o Censo Escolar pós-2021 é (a) um arquivo por aluno com identificadores suprimidos ou (b) genuinamente agregado por escola sem registro individual algum. **Status: disputado/não verificado** — só a inspeção direta de um arquivo de microdados real (2023–2025) resolveria isso, o que não foi feito neste run (ver Perguntas em aberto).
- **Acesso a dados desagregados por aluno:** existe uma via formal — o Serviço de Acesso a Dados Protegidos (Sedap) do INEP, regido pela Portaria nº 637/2019 e ampliado pela Portaria nº 312/2023, com acesso presencial na sede do INEP ou remoto em "núcleos Sedap" (universidades/institutos federais), mediante projeto de pesquisa aprovado e vedação a cópia/retransmissão dos dados [3][12]. A página oficial não especifica quais bases exatas (Censo Escolar desagregado? SAEB desagregado?) estão disponíveis por esse canal — lacuna não fechada.
- **Tamanho:** só há número oficial para o ENEM (1,4 GB / 3,39M registros em 2021) [14]; para o Censo Escolar, a única estimativa encontrada (~200 GB para 2007–2019 em CSV) vem de um projeto comunitário no GitHub, não do INEP — tratar como ordem de grandeza, não fato oficial [15].

## 3. Distribuições reais

Estas são as variáveis com maior aplicação direta na calibração do gerador — e onde ficam mais claras as lacunas.

**Evasão, abandono e reprovação (a variável mais bem calibrável).** Censo Escolar 2023, divulgado pelo MEC/INEP em 22/02/2024 [21], com confirmação independente pela Fundação Carlos Chagas [20] (**status: verificado** — duas fontes distintas, uma delas o próprio comunicado oficial MEC/INEP, concordam no valor):
- Ensino Fundamental: abandono ~3,0%.
- Ensino Médio: reprovação 3,9%, evasão 5,9% (abandono masculino 3,8% vs. feminino 2,9%).
- O INEP distingue oficialmente **abandono** (situação de fim de ano, dentro do Censo Escolar) de **evasão** (taxa de transição — o aluno não se rematricula no ano seguinte, mesmo sem ter sido classificado como abandono); os dois números não são a mesma métrica e não devem ser somados ou confundidos [22]. Um recorte de 2019/2020 (QEdu Conteúdos) mostra o padrão esperado: abandono 4,7% vs. evasão 6,9% no mesmo período — evasão sistematicamente maior [22]. **Confiança: média-alta** — o mecanismo conceitual está confirmado, mas nenhuma tabela primária do INEP foi lida linha a linha para reconciliar exaustivamente os dois indicadores por etapa/ano.
- Séries mais críticas (reprovação + abandono combinados, FCC via Censo Escolar) [20]: 3º ano EF 10,2%→1,3%(2020)→6,8%(2023); 6º ano EF 13,8%→2,4%→8,7%; **1º ano EM 21,3%→6,4%→16,4%**. Os valores de 2020 são um outlier pandêmico (promoção quase automática) e não devem ser usados como referência de "ano normal".
- Distorção idade-série (Censo Escolar 2023): 4,28 milhões de alunos, concentrados no Nordeste (35,9%) e Sudeste (27,8%); nos anos finais do EF, alunos pretos/pardos têm distorção quase o dobro da de brancos (20,9% vs. 10,8%) [20].
- Recorte por raça/gênero no Ensino Médio: evasão masculino 3,5% / feminino 2,6%; brancos 2,1% / pretos e pardos 3,5% (não confirmado se o recorte é específico do EM ou da educação básica agregada — confiança média) [20].
- PNAD Educação 2025 (IBGE): dado de 7,7 milhões de jovens de 14–29 anos sem concluir o EM, citado apenas por reportagem secundária (CartaCapital) — a página oficial da Agência IBGE retornou erro 403 e o PDF oficial "Educação 2025" é um infográfico em imagem sem texto extraível. **Status: não verificado** — nenhuma fonte primária do IBGE foi lida com este número específico [10].

**Notas (0–10) — sem base pública.** Nem o Censo Escolar nem o INEP coletam ou publicam notas de boletim; a única distribuição pública de desempenho é a **proficiência do SAEB**, numa escala de pontos (não 0–10) com 4 níveis categóricos (insuficiente/básico/proficiente/avançado). Dado 2023: 59% dos estudantes no último ano da educação básica estão em nível "Insuficiente" em Matemática; no 2º ano do EF, 49% dos alunos da rede pública estão alfabetizados contra 77% na rede privada [23]. **Confiança média** — via cobertura secundária do relatório SAEB 2023, cujo PDF primário não pôde ser aberto (erro de certificado SSL) em nenhuma das duas rodadas de pesquisa.

**Frequência diária — sem base pública.** Não existe indicador nacional de "% de presença por aula/dia". O único dado oficial de frequência é a **frequência líquida ajustada** da PNAD Contínua (adequação idade-etapa, ~98,9–100% no Fundamental, 80,6% no Médio) [9] — um conceito de acesso/permanência na idade certa, não de assiduidade cotidiana. Confundir os dois na calibração produziria uma taxa de frequência artificialmente alta e sem relação com "faltas consecutivas", que é o sinal que o Sinaliza precisa detectar.

**Atividades não entregues — sem base pública em nenhuma das quatro dimensões pesquisadas.** Confirmado de forma consistente nas duas rodadas de todas as dimensões: nenhuma base federal, estadual ou agregador (INEP, IBGE, QEdu) publica esse indicador. É dado operacional interno de sistemas de gestão escolar (LMS, SEDs estaduais), nunca consolidado nacionalmente.

## 4. Limitações e vieses

- **Defasagem estrutural de 9–12 meses entre coleta e publicação**, confirmada em dois ciclos distintos: SAEB/IDEB 2021 (coleta em 2021, resultados só em 16/09/2022, microdados só "até dezembro de 2022") [28], e o cronograma oficial do Censo Escolar 2026 (Portaria INEP nº 219/2026): coleta até 31/jul/2026, sinopses só em 01/fev/2027, indicadores de rendimento só em 14/mai/2027 [27]. Isso não é um episódio isolado — é o padrão do ciclo INEP. Um Fórum Nacional de Educação chegou a emitir nota formal criticando atraso do Censo Escolar 2024/SAEB 2023 [26].
- **Agregação mascara a variância individual**: nenhuma das três bases centrais (Censo Escolar, SAEB, IDEB) produz nota ou frequência por aluno de forma pública; o IDEB, por ser `Proficiência × Fluxo`, "não revela por que o fluxo é alto" nem "se a aprendizagem está distribuída equitativamente" — uma limitação que o próprio INEP reconhece na nota técnica de concepção do indicador [24].
- **Rupturas de comparabilidade sem mudança formal de metodologia**: a taxa de aprovação da rede pública saltou de 91,7% (2019) para 98,4% (2020) e ficou em 96,3% (2021) — não por mudança de fórmula do IDEB (que o MEC/INEP confirma ser a mesma desde 2007 [28]), mas por "ajustes nos critérios de aprovação" e adoção de "continuum curricular" em 72,3% e 17,2% das escolas, respectivamente, durante a pandemia [28]. É um alerta direto para quem for gerar cenários sintéticos "atípicos": promoção automática infla aprovação sem refletir aprendizagem real, e o próprio INEP recomenda cautela na leitura da série nesses anos [25][28].
- **Cobertura desigual rede pública vs. privada**: SAEB é obrigatório para escolas públicas e facultativo (mediante adesão paga) para privadas; a fonte oficial (perguntas frequentes do INEP) não publica o percentual de adesão privada nem confirma se a avaliação é censitária por rede — ou seja, qualquer comparação pública/privada nas bases oficiais carrega viés de autosseleção do lado privado, de magnitude não quantificada publicamente [29].
- **Qualidade dos dados autodeclarados**: o preenchimento do Censo Escolar (Educacenso) é feito pelas próprias escolas, e guias institucionais (Fundação Lemann/Undime) tratam explicitamente da qualificação de registros de frequência e da declaração de raça/cor como pontos de atenção reconhecidos [31]. A nota técnica oficial do IBGE sobre autodeclaração na PNAD Educação (NT 02/2022) foi localizada mas não pôde ser lida integralmente (bloqueio de acesso) — **gap não fechado** [30].
- **Acesso condicionado a canais formais**: análises mais desagregadas frequentemente exigem pedido via Lei de Acesso à Informação (LAI) ou projeto aprovado via Sedap, conforme nota técnica apresentada em audiência pública no Senado sobre o impacto da indisponibilidade de microdados do INEP [32].

---

## Insights entre dimensões

O fato que mais restringe a decisão de calibração não aparece isolado em nenhuma dimensão — só fica visível ao cruzá-las: a mudança de granularidade dos microdados do Censo Escolar pós-2021 (Seção 2) **é exatamente o motivo pelo qual** a Seção 3 não encontra nenhuma distribuição pública de notas ou frequência por aluno individual, apesar de essas variáveis existirem no desenho conceitual do Censo Escolar antes de 2021. Não é que o Brasil nunca tenha coletado esse dado — é que ele deixou de ser público, por decisão de política de privacidade, no mesmo período em que o gerador sintético do Sinaliza precisaria dele. Isso muda a natureza do trabalho de calibração: em vez de "amostrar de uma distribuição real anonimizada", o projeto precisa **inferir uma distribuição plausível por aluno a partir de taxas agregadas por escola/rede** — uma etapa de modelagem estatística adicional (ex.: assumir uma distribuição paramétrica por aluno que, agregada, reproduza as taxas oficiais por escola) que não seria necessária se os microdados de 2021+ ainda fossem por aluno.

Um segundo cruzamento: a ausência de dado público para "atividades não entregues" (Seção 3) e para "frequência diária" (Seção 3) não é uma lacuna de busca — é estrutural, porque nenhuma das bases (Seção 1) foi desenhada para medir isso: o Censo Escolar mede matrícula/situação final, o SAEB mede proficiência amostral, a PNAD mede adequação idade-etapa. Essas três variáveis do modelo do Sinaliza (`AttendanceRecord`, `AssignmentSubmission`) não têm — e estruturalmente não podem ter — um equivalente público brasileiro; só `Grade`/taxas de rendimento (via proxy de proficiência/abandono) e a lógica de `TrajectorySnapshot` (evasão/distorção) têm ancoragem estatística real.

## Recomendações

1. **Calibrar `TrajectorySnapshot`/evasão e a lógica de `FollowUp` com as taxas do Censo Escolar 2023** — abandono ~3% (EF) / evasão ~5,9% e reprovação ~3,9% (EM), com o 1º ano do EM tratado como subgrupo de risco elevado (~16–21% de insucesso combinado). Confiança alta — dado verificado por duas fontes independentes (MEC/INEP oficial + FCC) [20][21]. Usar abandono e evasão como duas variáveis distintas no gerador (não somar), documentando a definição de cada uma.
2. **Calibrar `Grade` por um proxy categórico de proficiência, não por uma distribuição real 0–10** — não existe fonte pública para distribuição de notas de boletim; usar os 4 níveis do SAEB (insuficiente/básico/proficiente/avançado, com ~59% em "insuficiente" em Matemática no fim da educação básica) como base para desenhar uma distribuição sintética 0–10 documentada como suposição de design, não como dado calibrado. Confiança média (fonte secundária sobre PDF primário não lido) [23].
3. **Tratar `AttendanceRecord` (frequência diária) e `AssignmentSubmission` (atividades não entregues) como suposições de design puras** — nenhuma fonte pública brasileira mede assiduidade cotidiana nem entrega de tarefas; usar a frequência líquida ajustada da PNAD (98,9–100% EF / 80,6% EM) apenas como referência de ordem de grandeza de "acesso à escola", nunca como proxy de "presença diária em sala" — são conceitos diferentes e confundi-los infla artificialmente a taxa de frequência simulada.
4. **Se o projeto precisar de granularidade por aluno para validar o gerador contra dado real (não apenas taxas agregadas), o único caminho formal é o Sedap do INEP** — requer projeto de pesquisa aprovado, não é um download direto; avaliar se vale o esforço institucional ou se a calibração por taxas agregadas (recomendações 1–3) já é suficiente para o objetivo de ~200 alunos fictícios.
5. **Ao publicar os números de calibração usados no gerador, registrar a fonte e a confiança ao lado de cada parâmetro** (ex. num comentário no seed/fixture) — dado o padrão desta pesquisa de vários números virem de fonte secundária por bloqueio técnico de acesso ao PDF primário do INEP, isso evita que uma suposição de design vire "fato" silenciosamente na base de código.

## Perguntas em aberto

- **O Censo Escolar pós-2021 tem ou não registro por aluno individual (com identificadores suprimidos) por trás do agregado publicado por escola?** O RIPD do INEP é ambíguo/contraditório nesse ponto entre suas próprias seções [3]. Só a inspeção direta de um arquivo de microdados real (2023–2025: contar linhas do arquivo "ALUNOS" vs. número de escolas) resolveria isso — não feito neste run.
- **Qual o delimitador exato e a estrutura de arquivo real dos microdados do Censo Escolar e do SAEB?** (pipe vs. vírgula, tamanho em GB/linhas) — só confirmado para o ENEM via RIPD primário; para as outras duas bases, apenas sínteses de busca sobre PDFs bloqueados por erro de certificado.
- **Qual o percentual oficial de adesão de escolas privadas ao SAEB?** Não publicado nas fontes oficiais acessadas; taxa de R$400–R$4.000 citada por fonte secundária de 2017 (domínio morto, não confirmável).
- **O que diz, na íntegra, a Nota Técnica 02/2022 do IBGE sobre autodeclaração na PNAD Educação?** Localizada, mas bloqueada ao acesso (403 / PDF ilegível) nas duas rodadas.
- **Quais bases exatas (Censo Escolar desagregado? SAEB desagregado?) estão disponíveis via Sedap?** A página oficial do INEP não especifica.
- **Existe alguma base estadual/municipal (RJ, MG, RS, ES) com granularidade além do espelho do INEP?** Portais localizados, datasets de educação não inspecionados dentro do orçamento deste run.

Cada um resolveria uma lacuna concreta de calibração; nenhum foi perseguido além do orçamento de 2 rodadas por dimensão aprovado no plano gate — ficam como trabalho de um Deepen futuro, se o projeto precisar de mais precisão do que taxas agregadas oferecem.

## Apêndice de fontes

| # | Suporta | Publisher | Data pub. | Acessado | Confiança |
|---|---|---|---|---|---|
| [1] | Censo Escolar: o que mede, granularidade histórica, licença | [INEP — Censo Escolar (microdados)](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar) | s/d | 2026-09-17 | alta |
| [2] | Exclusão de microdados do Censo Escolar pós-2021 (contexto) | [Centro de Referências em Educação Integral](https://educacaointegral.org.br/reportagens/por-que-exclusao-de-dados-do-censo-escolar-e-um-problema/) | s/d | 2026-09-17 | média |
| [3] | RIPD dos Censos da Educação — agregação por escola, risco de reidentificação, Sedap | [INEP — RIPD dos microdados dos Censos da Educação](https://download.inep.gov.br/microdados/RIPD_dos_microdados_dos_Censos_da_Educa%C3%A7%C3%A3o.pdf) | 2022-12-30 | 2026-09-17 | alta (fonte primária lida integralmente) |
| [4] | Confirmação independente da remoção de microdados pós-2021 | [Correio Braziliense — Inep remove microdados do Censo Escolar e do Enem](https://www.correiobraziliense.com.br/euestudante/enem/2022/02/4987511-inep-remove-microdados-do-censo-escolar-e-do-enem-e-oculta-informacoes.html) | 2022-02 | 2026-09-17 | alta (fonte independente) |
| [5] | Nota oficial de esclarecimento do INEP sobre divulgação dos microdados | [INEP — Nota de esclarecimento](https://www.gov.br/inep/pt-br/centrais-de-conteudo/noticias/institucional/nota-de-esclarecimento-divulgacao-dos-microdados) | s/d | 2026-09-17 | alta |
| [6] | IDEB: fórmula, granularidade, periodicidade | [INEP — Ideb](https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb) | s/d | 2026-09-17 | alta |
| [7] | SAEB: o que mede, amostragem, licença, edições | [INEP — Saeb](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/saeb) | s/d | 2026-09-17 | alta |
| [8] | QEdu: metodologia de taxas de rendimento, replica cálculo oficial | [QEdu — Brasil, Taxas de Rendimento](https://qedu.org.br/brasil/taxas-rendimento) / [Academia QEdu](https://academia.qedu.org.br/censo-escolar/taxa-de-rendimento/) | s/d | 2026-09-17 | média |
| [9] | PNAD Contínua Educação: frequência líquida ajustada, cobertura | [IBGE — PNAD Contínua](https://www.ibge.gov.br/estatisticas/sociais/educacao/17270-pnad-continua.html) | s/d | 2026-09-17 | média |
| [10] | PNAD Educação 2025 — 7,7 milhões de jovens sem concluir o EM (não confirmado na fonte primária) | [CartaCapital](https://www.cartacapital.com.br/educacao/87-milhoes-de-jovens-brasileiros-abandonaram-ou-nunca-frequentaram-a-escola-mostra-ibge/) | 2025/2026 | 2026-09-17 | baixa |
| [11] | Portal estadual de dados abertos (SP) — indicadores próprios (IDESP/SARESP) | [Dados Abertos da Educação — SP](https://dados.educacao.sp.gov.br/) | s/d | 2026-09-17 | média |
| [12] | Sedap — canal formal de acesso a dados protegidos/desagregados | [INEP — Serviço de Acesso a Dados Protegidos (Sedap)](https://www.gov.br/inep/pt-br/areas-de-atuacao/gestao-do-conhecimento-e-estudos-educacionais/cibec/servico-de-acesso-a-dados-protegidos-sedap) | s/d | 2026-09-17 | alta |
| [13] | Metodologia oficial de cálculo das taxas de rendimento | [INEP — Nota Técnica 002/2010](https://download.inep.gov.br/download/censo/2009/NT_indicadores_rendimento2009.pdf) | 2010 | 2026-09-17 | alta |
| [14] | RIPD do ENEM — formato, tamanho, técnica de anonimização | [INEP — RIPD dos microdados do Enem](https://download.inep.gov.br/microdados/RIPD_dos_microdados_do_Enem.pdf) | 2022-12-21 | 2026-09-17 | alta (fonte primária lida integralmente) |
| [15] | Estimativa de tamanho dos microdados do Censo Escolar (não oficial) | [GitHub — paeselhz/microdados_censo_escolar](https://github.com/paeselhz/microdados_censo_escolar) | s/d | 2026-09-17 | baixa |
| [16] | Como consultar o IDEB por escola (painel, não microdado) | [MEC — Confira como acessar os resultados do Ideb por escola](https://portal.mec.gov.br) | 2026-08 | 2026-09-17 | média |
| [17] | ANPD — fiscalização da divulgação de microdados pelo INEP | [ANPD — Nota Técnica nº 12/2023-CGF/ANPD/INEP](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/documentos-tecnicos-orientativos/nota-tecnica-no-12-2023-cgf-anpd-inep.pdf) | 2023 | 2026-09-17 | média |
| [18] | LGPD e microdados de educação — variáveis suprimidas | [IEDE — Nota Técnica LGPD](https://portaliede.org.br/wp-content/uploads/2024/06/Nota_Tecnica_LGPD.pdf) | 2024 | 2026-09-17 | média |
| [19] | Portal SP — dataset é espelho do INEP, sem licença própria | [Dados Abertos SP](https://dadosabertos.sp.gov.br/painel) | s/d | 2026-09-17 | média |
| [20] | Censo Escolar 2023 — abandono/reprovação/evasão, distorção idade-série | [Fundação Carlos Chagas — Censo Escolar 2023](https://www.fcc.org.br/fcc-noticia/censo-escolar-2023-reprovacao-e-abandono-retomam-crescimento-apos-pandemia/) | 2024 | 2026-09-17 | alta (corroborado por [21]) |
| [21] | Confirmação oficial MEC/INEP dos números do Censo Escolar 2023 | [MEC/INEP — Resultados do Censo Escolar 2023](https://www.gov.br/inep/pt-br/assuntos/noticias/censo-escolar/mec-e-inep-divulgam-resultados-do-censo-escolar-2023) | 2024-02-22 | 2026-09-17 | alta (fonte primária) |
| [22] | Distinção oficial abandono vs. evasão (taxas de transição) | [QEdu Conteúdos / IEDE](https://portaliede.org.br/contribuicao/qedu-disponibiliza-taxas-de-rendimento-2023-para-cada-um-dos-anos-escolares/) | 2024 | 2026-09-17 | média |
| [23] | SAEB 2023 — % em nível "insuficiente", alfabetização por rede | [INEP — Relatório SAEB 2023 Volume 1](https://download.inep.gov.br/saeb/resultados/relatorio-saeb_volume_1_2023.pdf) (via cobertura secundária) | 2024 | 2026-09-17 | média |
| [24] | IDEB não revela distribuição de aprendizagem nem causa do fluxo | [INEP — Nota Técnica nº 1, Concepção do IDEB](https://download.inep.gov.br/educacao_basica/portal_ideb/o_que_e_o_ideb/Nota_Tecnica_n1_concepcaoIDEB.pdf) | s/d | 2026-09-17 | média |
| [25] | Distorções de composição amostral SAEB/IDEB 2021 | [Observatório do Movimento pela Base](https://observatorio.movimentopelabase.org.br/distorcoes-saeb-ideb-2021/) | 2021/2022 | 2026-09-17 | média |
| [26] | Atraso na divulgação de dados do INEP (Censo Escolar/SAEB) | [ANPEd — Nota do Fórum Nacional de Educação](https://anped.org.br/nota-do-forum-nacional-de-educacao-sobre-o-atraso-da-divulgacao-de-dados-produzidos-pelo-inep/) | 2025 | 2026-09-17 | média |
| [27] | Cronograma oficial do Censo Escolar 2026 (defasagem ~9-10 meses) | [Conviva Educação — Portaria INEP nº 219/2026](https://convivaeducacao.org.br/fique_atento/6106) | 2026 | 2026-09-17 | média (reproduz portaria oficial) |
| [28] | Divulgação SAEB/IDEB 2021, mesma metodologia desde 2007, aprovação inflada na pandemia | [MEC/INEP — Divulgação Saeb e Ideb 2021](https://www.gov.br/mec/pt-br/assuntos/noticias/2022/mec-e-inep-divulgam-resultados-do-saeb-e-do-ideb-2021) | 2022-09-16 | 2026-09-17 | alta |
| [29] | Adesão de escolas privadas ao SAEB (facultativa, sem % público) | [INEP — Perguntas frequentes sobre o Saeb](https://www.gov.br/inep/pt-br/acesso-a-informacao/perguntas-frequentes/sistema-de-avaliacao-da-educacao-basica-saeb) | s/d | 2026-09-17 | alta |
| [30] | Nota técnica do IBGE sobre autodeclaração na PNAD Educação (não lida integralmente) | [IBGE — Notas técnicas PNAD Contínua Educação 2020/2021](https://www.ibge.gov.br/novo-portal-destaques/34430-notas-tecnicas-pnad-continua-educacao-em-2020-e-2021) | 2022 | 2026-09-17 | baixa (não lida na íntegra) |
| [31] | Qualidade de preenchimento do Educacenso pelas escolas | [Fundação Lemann/Undime — Guia Censo Escolar e Declaração Racial](https://fundacaolemann.org.br/wp-content/uploads/2025/07/Guia-Censo-Escolar-e-Declaracao-Racial-Fundacao-Lemann-e-Undime.pdf) | 2025 | 2026-09-17 | média |
| [32] | Impacto da indisponibilidade de microdados do INEP (audiência Senado) | [Campanha Nacional pelo Direito à Educação](https://media.campanha.org.br/acervo/documentos/NotaTecnica_DadosInep_BalancoPNE_2023_10_26_AudienciaPublica-CE-Senado.docx.pdf) | 2023 | 2026-09-17 | média |
| [33] | Busca Ativa Escolar — ferramenta operacional, não base pública nacional | [UNICEF Brasil — Busca Ativa Escolar](https://www.unicef.org/brazil/busca-ativa-escolar) | s/d | 2026-09-17 | média |

## Mapa de obsolescência

Computado por `recon_kit.py staleness` (não estimado à mão) a partir do ledger de claims carga-crítica do memlog, com janelas por classe: `fato oficial (fonte primária)` → 12 meses · `metodologia oficial` → 24 meses · `número estatístico` (taxas de evasão/abandono/proficiência) → 6 meses · `processo/acesso institucional` (Sedap, licenças) → 12 meses.

| Claim | Classe | Publicado | Reverificar até | Status |
|---|---|---|---|---|
| RIPD Censo Escolar pós-2021 agregado por escola (LGPD) [3][4][5] | fato oficial (fonte primária) | 2022-12 | 2023-12-01 | vencido |
| Censo Escolar 2023 — abandono/evasão/reprovação [20][21] | número estatístico | 2024-02 | 2024-08-01 | vencido |
| SAEB 2023 — % nível insuficiente, alfabetização [23] | número estatístico | 2024-01 | 2024-07-01 | vencido |
| PNAD Educação 2025 — 7,7 milhões sem concluir EM [10] | número estatístico | 2025-06 | 2025-12-01 | vencido |
| Sedap — processo de acesso [12] | processo/acesso institucional | 2023-07 | 2024-07-01 | vencido |
| Metodologia do IDEB (Proficiência × Fluxo), reafirmada em 2022 [6][24][28] | metodologia oficial | 2022-09 | 2024-09-01 | vencido |
| RIPD do ENEM — formato/tamanho/anonimização [14] | fato oficial (fonte primária) | 2022-12 | 2023-12-01 | vencido |
| Licença CC BY-ND 3.0 dos microdados do INEP [1] | processo/acesso institucional | 2020-01 | 2021-01-01 | vencido |
| SAEB — adesão facultativa da rede privada [29] | fato oficial (fonte primária) | 2020-01 | 2021-01-01 | vencido |
| Defasagem estrutural de 9–12 meses coleta→publicação (Censo Escolar 2026) [27] | processo/acesso institucional | 2026-06 | 2027-06-01 | dentro da janela |

**9 das 10 claims carga-crítica já estão fora da janela de reverificação recomendada** (a única dentro da janela é o cronograma do Censo Escolar 2026, publicado há 3 meses). A mais antiga vencida é a data-base 2020/2022 (licença e adesão privada do SAEB, reverificar desde 2021-01); a mais relevante para a calibração numérica é o Censo Escolar 2023/SAEB 2023, vencidos desde 2024. **Antes de usar estes valores para calibrar o gerador em produção, checar se o Censo Escolar 2024/2025 e um eventual SAEB 2025 já publicaram taxas de rendimento e proficiência mais recentes** — não verificado neste run (ver Perguntas em aberto). Isso é esperado para uma primeira pesquisa sobre bases cuja atualização mais recente (Censo Escolar 2025) só saiu em julho/2026 — o mapa aponta o quê reverificar, não que os dados estejam errados.
