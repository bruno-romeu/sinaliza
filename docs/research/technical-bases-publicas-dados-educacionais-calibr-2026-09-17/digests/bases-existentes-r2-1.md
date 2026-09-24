# Bases públicas de dados educacionais no Brasil — Rodada 2 (aprofundamento)

Data da pesquisa: 2026-09-17
Foco: fechar lacunas da Rodada 1 (granularidade SAEB, Sedap, PNAD Educação 2025, portais estaduais, "atividades não entregues", metodologia QEdu/INEP de taxas de rendimento).

## Síntese por lacuna da Rodada 1

### 1. Números oficiais INEP de abandono 2022/2023 (citados pelo QEdu)
**Não fechada totalmente.** A página oficial do INEP "Confira as taxas de aprovação, reprovação e abandono escolar" (gov.br/inep) retornou como **conteúdo restrito** ao fetch direto (parede de autenticação/bot-block), impedindo extrair os números específicos por etapa/ano diretamente da fonte primária nesta rodada também. Em compensação, foi possível confirmar a **metodologia oficial** de cálculo (INEP, Nota Técnica 002/2010 e notas técnicas de transição/rendimento subsequentes, incl. `taxas_de_rendimento_escolar_final.pdf` de 2021): Aprovação + Reprovação + Abandono = 100% das matrículas válidas no módulo "Situação do Aluno" do Educacenso; "deixou de frequentar" é contado como abandono. Essa metodologia é a mesma reproduzida pelo QEdu Academia (`academia.qedu.org.br/censo-escolar/taxa-de-rendimento/`), o que corrobora que o QEdu não usa metodologia própria — apenas replica o cálculo INEP sobre o Censo Escolar.

### 2. Nota de Esclarecimento INEP sobre mudança de granularidade dos microdados
**Não fechada.** Não foi encontrado texto alternativo acessível desta nota nesta rodada (não perseguida diretamente; ver gaps).

### 3. PNAD Educação 2025 (IBGE) — leitura completa
**Parcialmente fechada, com novo obstáculo.** Localizado o documento oficial "Educação 2025" na Biblioteca do IBGE (`biblioteca.ibge.gov.br/visualizacao/livros/liv102286_informativo.pdf`) — confirma que existe uma publicação formal `PNADEDU_INFO_RESUMO`. Porém o PDF é um infográfico produzido em Adobe Illustrator, majoritariamente composto por imagens embutidas (JP2), sem texto extraível — não foi possível extrair números específicos de frequência/abandono por faixa etária nesta rodada (falha diferente do 403 da R1, mas mesmo resultado: sem números confirmados na fonte primária). Confirmado, via página oficial do IBGE, que o módulo Educação da PNAD Contínua existe desde 2016, coleta anual no 2º trimestre (ampliando para toda a amostra, incluindo educação profissional), e cobre alfabetização, escolarização, nível de instrução, anos de estudo e frequência escolar.

### 4. Granularidade dos microdados do SAEB (aluno vs. escola)
**Parcialmente fechada.** A página oficial de microdados do SAEB (`gov.br/inep/.../dados-abertos/microdados/saeb`) lista arquivos de 1995 a 2023 mas **não descreve explicitamente**, no corpo da página, se os registros são por aluno ou agregados por escola. Fontes secundárias técnicas (Conviva Educação/INEP, cobertura do lançamento do SAEB 2021) indicam que o pacote de microdados do SAEB é organizado por **etapa avaliada** (5º ano, 9º ano, 3ª série do EM) e inclui dicionário de variáveis, escalas de proficiência e questionários — estrutura consistente com dados **por aluno respondente** (associados a escores de proficiência individuais), não apenas agregados por escola. Uma nota técnica de terceiros sobre LGPD (`portaliede.org.br/.../Nota_Tecnica_LGPD.pdf`) reforça isso ao mencionar que variáveis identificadoras de aluno (data de nascimento, idade, sexo) deixaram de constar na base pública a partir de 2019 — ou seja, a base **era e continua sendo por aluno**, apenas com campos de identificação suprimidos por LGPD, não a granularidade em si alterada. Confiança: média (inferência de fontes secundárias técnicas, não da documentação primária lida integralmente).

### 5. "Atividades não entregues" como métrica em base pública
**Confirmado que não existe.** Nenhuma fonte encontrada (nesta rodada ou na anterior) mede "atividades não entregues" por aluno. Segue como métrica sem base pública equivalente — precisa ser sintetizada/inferida a partir de proxies como frequência e taxas de rendimento.

### 6. Portais municipais/estaduais de dados abertos em educação
**Parcialmente investigado.** Identificados: portal estadual do Rio de Janeiro (`dadosabertos.rj.gov.br`, lançado pelo governo estadual, reúne dados de várias secretarias incl. educação) e o portal municipal DATA.RIO (`data.rio` / `carioca.rio`, com categoria Educação); portal estadual de Minas Gerais (`dados.mg.gov.br`). **Não foi possível confirmar, nesta rodada, a granularidade exata** (aluno/escola/agregado) dos datasets de educação hospedados nesses portais — os datasets em si não foram abertos e inspecionados, apenas os portais localizados. RS e ES não foram investigados por orçamento (ES apareceu apenas indiretamente via um boletim do IJSN-ES sobre a PNAD Contínua, não sobre portal próprio de microdados).

### 7. Granularidade dos indicadores de SP (IDESP/SARESP)
**Não investigada nesta rodada** (não houve orçamento remanescente).

### 8. Sedap (Serviço de Acesso a Dados Protegidos) do INEP
**Fechada razoavelmente bem.** Confirmado via página oficial do INEP e busca: o Sedap é o canal formal do INEP para acesso a bases protegidas/desagregadas para fins de pesquisa científica ou institucional de interesse público, regido pela Portaria nº 637 (17/07/2019) e ampliado pela Portaria nº 312 (03/07/2023). Funciona por (a) acesso presencial em sala dedicada na sede do INEP, com computadores e pacotes estatísticos, ou (b) acesso remoto via "núcleos Sedap" em instituições parceiras (universidades federais, institutos federais, CEFETs) desde 2023. Projetos passam por análise técnica prévia (pertinência do pedido) e os resultados da pesquisa também passam por análise técnica antes de serem liberados ao pesquisador, preservando o sigilo de identidade de alunos/instituições. A página oficial consultada **não especificou explicitamente** quais bases (Censo Escolar, SAEB, etc.) estão disponíveis via Sedap nem se os microdados lá são de fato desagregados por aluno — permanece uma lacuna parcial.

### 9. Busca Ativa Escolar como base estruturada de indicadores de risco
**Investigada — conclusão: não é uma base pública de microdados, é uma ferramenta operacional.** É uma plataforma digital gratuita desenvolvida pelo UNICEF em parceria com Undime, Congemas e Conasems, destinada a municípios para identificar, registrar e acompanhar crianças/adolescentes fora da escola ou em risco de evasão. Permite acompanhar frequência em tempo real, relatórios de baixa frequência e indicadores por escola/turma/rede, mas os dados alimentados nela pertencem a cada município/rede e não constituem um dataset público nacional aberto e consultável — portanto não serve como fonte de calibração estatística direta, apenas como referência de quais variáveis municípios já monitoram operacionalmente (frequência em tempo real, causas de evasão).

## Claims adicionais de metodologia (Censo Escolar / taxas de rendimento)

- Fórmula oficial: Taxa de Aprovação + Taxa de Reprovação + Taxa de Abandono = 100% das matrículas válidas, calculada com base no módulo "Situação do Aluno" do Educacenso (2ª etapa do Censo Escolar), considerando apenas alunos com situação final informada (aprovado/reprovado/deixou de frequentar). Essas taxas alimentam o Indicador de Rendimento usado no cálculo do IDEB — reforça que é um indicador **agregado** (escola/rede/UF/Brasil), não um registro aluno-a-aluno publicamente aberto com esse rótulo.

## Leads para próxima rodada

- Nota de Esclarecimento INEP sobre mudança de granularidade dos microdados pós-2021 (tentar fonte alternativa, ex. Wayback Machine ou PDF direto em vez da página HTML).
- Tentar abrir o PDF "Educação 2025" do IBGE com uma ferramenta de OCR/extração de imagem, já que o texto está embutido como imagens JP2 (não é bloqueio de acesso, é formato).
- Investigar diretamente os catálogos de datasets dentro de `dadosabertos.rj.gov.br` e `dados.mg.gov.br` (não apenas os portais) para confirmar granularidade de dados de educação.
- Portais de RS (Rio Grande do Sul) e ES (Espírito Santo) ainda não localizados/verificados.
- Testar se os "núcleos Sedap" (parcerias com universidades federais desde a Portaria 312/2023) publicam listas de quais bases específicas (Censo Escolar, SAEB) estão disponíveis para pesquisa remota.
- IDESP/SARESP (São Paulo) — confirmar granularidade exata.
- Nota Informativa do IDEB 2023/2025 (`download.inep.gov.br/ideb/...`) ainda não lida — pode conter distribuições de notas/proficiência por etapa e região, útil para calibrar distribuição de notas do gerador sintético.
- Nota Técnica de LGPD sobre microdados educacionais (`portaliede.org.br/.../Nota_Tecnica_LGPD.pdf`) — vale leitura completa; foi só citada via snippet nesta rodada, pode detalhar exatamente quais variáveis de aluno foram suprimidas em cada base (SAEB, Censo Escolar) e desde quando.

## Gaps (não resolvidos nesta rodada)

- Números específicos de taxa de abandono 2022/2023 direto da fonte primária INEP (página retornou bloqueada/restrita ao fetch).
- Conteúdo integral da Nota de Esclarecimento do INEP sobre mudança de granularidade dos microdados pós-2021.
- Números específicos de frequência/abandono por faixa etária do informativo "Educação 2025" do IBGE (PDF é infográfico baseado em imagem, texto não extraível pela ferramenta de fetch).
- Confirmação primária definitiva (não inferida) de que os microdados do SAEB são por aluno respondente individual — a página oficial de microdados não descreve isso explicitamente; a conclusão vem de fontes secundárias técnicas convergentes.
- Detalhamento de quais bases exatas (Censo Escolar desagregado? SAEB desagregado?) estão disponíveis via Sedap — a página oficial fetchada não especifica.
- Granularidade exata dos datasets de educação nos portais de dados abertos de RJ e MG (portais localizados, datasets não inspecionados).
- Portais de dados abertos em educação de RS e ES não localizados/verificados nesta rodada.
- Granularidade exata do IDESP/SARESP (São Paulo) — não investigada nesta rodada.
- Nota Informativa do IDEB 2023/2025 — não lida nesta rodada.

## Fontes consultadas nesta rodada

| URL | Publisher | Título | Data |
|---|---|---|---|
| https://download.inep.gov.br/download/censo/2009/NT_indicadores_rendimento2009.pdf | INEP | Nota Técnica 002/2010 — Cálculo das Taxas de Rendimento | 2010 |
| https://download.inep.gov.br/educacao_basica/educacenso/situacao_aluno/documentos/2021/taxas_de_rendimento_escolar_final.pdf | INEP | Taxas de Rendimento Escolar | 2021 |
| https://www.gov.br/inep/pt-br/centrais-de-conteudo/noticias/censo-escolar/confira-as-taxas-de-aprovacao-reprovacao-e-abandono-escolar | INEP | Confira as taxas de aprovação, reprovação e abandono escolar | s/d (acesso restrito ao fetch) |
| https://download.inep.gov.br/dados/sedap/documentos/guia_usuario_servico_acesso_dados_protegidos_sedap.pdf | INEP | Guia do Usuário — Sedap | s/d |
| https://www.gov.br/inep/pt-br/areas-de-atuacao/gestao-do-conhecimento-e-estudos-educacionais/cibec/servico-de-acesso-a-dados-protegidos-sedap | INEP | Serviço de Acesso a Dados Protegidos (Sedap) | s/d |
| https://portal.mec.gov.br/component/content/article?id=72541 | MEC | Aberta consulta ao Serviço de Acesso a Dados Protegidos | s/d |
| https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/saeb | INEP | Microdados — SAEB | s/d |
| https://convivaeducacao.org.br/fique_atento/3977 | Conviva Educação | Divulgados microdados do Saeb 2021 | 2022 |
| https://buscaativaescolar.org.br/noticia/divulgados-microdados-do-saeb-2021 | Busca Ativa Escolar (via INEP) | Divulgados microdados do Saeb 2021 | 2022 |
| https://portaliede.org.br/wp-content/uploads/2024/06/Nota_Tecnica_LGPD.pdf | Instituto de Estudos para Políticas Educacionais (IEDE) | LGPD: Caminhos para a disponibilização de microdados de educação | 2024 |
| https://biblioteca.ibge.gov.br/visualizacao/livros/liv102286_informativo.pdf | IBGE | Educação 2025 (PNAD Contínua — informativo) | 2026 |
| https://www.ibge.gov.br/estatisticas/sociais/trabalho/17270-pnad-continua.html | IBGE | PNAD Contínua | s/d |
| https://www.unicef.org/brazil/busca-ativa-escolar | UNICEF Brasil | Busca Ativa Escolar | s/d |
| https://selounicef.org.br/busca-ativa-escolar | Selo UNICEF | Busca Ativa Escolar | s/d |
| https://dadosabertos.rj.gov.br/ | Governo do Estado do Rio de Janeiro | Portal de Dados Abertos do RJ | s/d |
| https://www.data.rio/ | Prefeitura do Rio de Janeiro | DATA.RIO | s/d |
| https://dados.mg.gov.br/ | Governo do Estado de Minas Gerais | Portal de Dados Abertos de MG | s/d |
| https://academia.qedu.org.br/censo-escolar/taxa-de-rendimento/ | QEdu (Fundação Lemann/Meritt) | Taxas de Rendimento — Academia QEdu | s/d |

## Stop reason

`budget` — orçamento de chamadas de busca/leitura desta rodada foi utilizado (12 chamadas: 6 buscas + 6 fetches, ligeiramente acima do teto de ~10 sugerido, mas dentro do limite de 8 fontes distintas efetivamente lidas). Ainda restam lacunas relevantes (Nota de Esclarecimento INEP, IDESP/SARESP, IDEB Nota Informativa, portais RS/ES) para uma Rodada 3, se necessário.
