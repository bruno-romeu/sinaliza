# Acesso e Formato — Bases Públicas de Dados Educacionais (Rodada 2)

Data: 2026-09-17
Foco: fechar lacunas da Rodada 1 sobre anonimização/LGPD (ANPD, RIPD), formato exato de arquivos, Sedap, ENEM, portais estaduais.

## Achados principais

### 1. RIPD do ENEM (fonte primária lida por completo) — anonimização, formato, tamanho

Documento: "Relatório de Impacto à Proteção de Dados Pessoais dos Microdados do ENEM", INEP, 21/12/2022.
URL: https://download.inep.gov.br/microdados/RIPD_dos_microdados_do_Enem.pdf

- **Formato confirmado**: os microdados do ENEM são distribuídos como "base de dados em formato CSV" dentro de um pacote compactado único (arquivo zip), junto com dicionário de dados, tabela de itens/parâmetros e programas de INPUT (SAS/SPSS).
- **Tamanho real (2021, última edição divulgada até a data do relatório)**: 3.389.832 registros de participantes, **volume de 1,4 GB**.
- **Quantidade de campos**: 76 dados pessoais por registro, sendo 1 sensível (cor/raça).
- **Técnica de anonimização usada**: não é k-anonimato formal, e sim um mix de **supressão de variáveis** + **generalização de categoria**, decidido internamente pelo INEP (DAEB/CGMEB) via Notas Técnicas 14/2021 e 10/2022/CGIM/DAEB, a partir do modelo "simplificado" adotado desde o ENEM 2020:
  - Exclusão da variável CO_ESCOLA (código da escola de conclusão do ensino médio) — motivo explícito: permitia reidentificação por gestores escolares via "ENEM por Escola" feito por terceiros.
  - Exclusão das variáveis de atendimento especializado/específico e dos recursos correspondentes (dados sensíveis de deficiência) — pequeno número de solicitantes tornava a combinação identificável.
  - Substituição de NU_IDADE (idade exata) por **faixa etária** categórica.
  - Exclusão de município/UF de nascimento e de residência do participante (mantém-se apenas o município do local de aplicação da prova).
  - Cor/raça foi **mantida** (considerada de baixo risco por ter categorias com alto volume de indivíduos).
  - O número de inscrição é substituído por uma **máscara** (não há CPF, nome, nome da mãe, data de nascimento exata, endereço, e-mail).
- **Editions disponíveis para download público**: 1998 a 2021 (na data do relatório, dez/2022).
- **Base de origem interna**: dados vêm das tabelas INT_ENM_INSCRICAO, INT_ENM_PROVA, INT_ENM_QUESTIONARIO, INT_ENM_RESULTADO (biblioteca DATA_ENEM, SAS), mantidas em pastas de rede corporativa acessíveis só pela CGMEB.
- **Contexto ANPD**: o RIPD foi solicitado pela ANPD via **Nota Técnica nº 46/2022/CGF/ANPD** (Ofício 22/2022/GABPR/ANPD/PR), com base no art. 38 da LGPD. A ANPD concluiu que "o INEP possui hipótese legal para realizar o tratamento consistente na divulgação dos microdados", desde que adotadas salvaguardas (ex.: acesso restrito a cadastrados, termos de responsabilidade). A CGU (Nota Técnica 1136/2022/CGAT/DTC/STPC) recomendou manter as bases publicadas "mesmo que haja dúvidas sobre sua correta anonimização", exceto se surgirem evidências de risco significativo.

### 2. RIPD dos Censos da Educação (Censo Escolar + Censo da Educação Superior) — fonte primária lida por completo

Documento: "Relatório de Impacto à Proteção de Dados Pessoais dos Microdados dos Censos da Educação", INEP, 30/12/2022.
URL: https://download.inep.gov.br/microdados/RIPD_dos_microdados_dos_Censos_da_Educa%C3%A7%C3%A3o.pdf

- **Dado coletado internamente por aluno (Educacenso) é muito mais rico que qualquer microdado público**: inclui CPF, NIS (Número de Identificação Social, carregado do CadÚnico até 2021), número da matrícula da certidão de nascimento, nome completo dos pais/responsáveis, data de nascimento, UF/município de nascimento, cor/raça, deficiência/TEA/altas habilidades, turma, transporte escolar, tipo de atendimento especializado. Nada disso está nos microdados públicos — é dado interno de gestão do Educacenso.
- **Achado mais relevante para a decisão de calibração — POSSÍVEL MUDANÇA DE GRANULARIDADE**: o RIPD afirma textualmente que o INEP "estruturou um novo modelo de arquivos de microdados públicos (**agregados por escolas** para o Censo Escolar da Educação Básica e **por curso** para o Censo da Educação Superior)" como técnica de controle de divulgação estatística, citando que "um impacto conhecido dessa abordagem é a redução do volume de informação disponível através do produto". Isso é uma frase direta do RIPD (dez/2022), e **conflita** com o que outras buscas (não primárias) desta e da rodada anterior sugerem — que os microdados do Censo Escolar continuam organizados por formulário de coleta (escolas, turmas, **alunos**, profissionais, gestores) "detalhados para a menor unidade de informação". **Não consegui reconciliar essa tensão nesta rodada** — é possível que (a) a agregação por escola tenha sido uma medida transitória/parcial revista depois pela NT 12/2023-CGF/ANPD/INEP citada na Rodada 1, ou (b) o texto do RIPD descreva apenas uma característica de determinados produtos, mantendo arquivos "ALUNOS" com registro por aluno mas variáveis diretamente identificadoras suprimidas (análogo ao modelo do ENEM). **Isso precisa ser verificado baixando e inspecionando um arquivo real de microdados do Censo Escolar 2023-2024 (contar linhas do arquivo de alunos vs. número de escolas) antes de assumir qualquer granularidade para a calibração.**
- **Técnicas de controle de divulgação estatística citadas como cardápio geral** (não todas necessariamente aplicadas ao Censo Escolar): agregação para níveis menos detalhados, generalização de categorias de variáveis, supressão de informações identificadoras, divulgação de bases amostrais, e privacidade diferencial ("ainda carecendo de uma aplicação de consenso" — ou seja, NÃO é usada atualmente pelo INEP).
- **Avaliação de risco formal registrada no RIPD**: risco de reidentificação nos microdados públicos dos Censos da Educação foi classificado como "elevado" (probabilidade e impacto) no formato antigo; após (1) alteração da estrutura dos arquivos e (2) acesso controlado via Sedap, o risco residual caiu para "médio" (aprovado) e, com as duas medidas combinadas, para "baixo".
- **Volume de titulares tratados**: considerando Censo Escolar + Censo da Educação Superior juntos, o INEP trata dados de **aproximadamente 60 milhões de brasileiros por ano** (discentes, docentes, gestores), com taxa de renovação da base da ordem de 10%/ano e taxa de crescimento de ~1%/ano.
- **Base técnica da decisão**: estudo contratado com o Departamento de Ciência da Computação da UFMG para mensuração objetiva do risco de reidentificação, mais Nota Técnica nº 05/2021/CGCQTI/DEED (encarregado de dados do INEP).
- **Coleta de dados pessoais identificados começou em 2007 (Censo Escolar) e 2009 (Censo da Educação Superior)** — antes disso as pesquisas não eram nominais.
- **Sedap** (Serviço de Acesso a Dados Protegidos, desde 2014) é citado no RIPD como o canal para pesquisa que precisa de granularidade/variáveis não disponíveis no microdado público — ou seja, é a via formal para acessar dados mais identificáveis mediante projeto de pesquisa aprovado.

### 3. Formato prático confirmado do Censo Escolar (fonte secundária consistente, não lida em PDF primário nesta rodada)

- Busca aponta que os microdados do Censo Escolar são "estruturados em formato CSV, com dados delimitados por Pipe (|)", com pacote incluindo Dicionário de Dados (xlsx), Tabelas Auxiliares (xlsx), Leia-Me (pdf), Filtros de Dados (pdf) e Formulários de Coleta (pdf). Isso é consistente com o que a Rodada 1 já havia levantado, mas **ainda não foi verificado por leitura direta de um arquivo real ou do "Leia-Me" oficial** (fetch ao PDF de notas estatísticas continuou falhando nesta rodada).
- Página oficial https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados (fonte primária, fetch com sucesso) confirma que Censo Escolar, SAEB, ENEM, Enade e Encceja têm microdados públicos, mas **não especifica formato de arquivo nem tamanho na própria página** — essas informações estão nas subpáginas/pacotes de cada base, que não pude abrir com sucesso nesta rodada (bloqueios/timeouts).
- Licença: o rodapé do site gov.br do INEP (e do portal estadual de SP) indica "Creative Commons Atribuição-SemDerivações 3.0 Não Adaptada" como licença geral do conteúdo do site — mas **não está confirmado que essa licença se aplique especificamente aos arquivos de microdados** (pode ser só a licença editorial do portal). Tratar como confiança média/baixa até confirmação direta no Leia-Me do pacote de microdados.

### 4. SAEB — formato (fonte secundária, síntese de busca; fetch direto à página oficial não tentado com sucesso nesta rodada)

- Pacote de microdados do SAEB inclui dados em CSV, dicionário, "Leia-Me", documentos técnicos, matrizes de referência, escalas de proficiência, questionários, planilhas de resultados e "inputs" (programas de leitura para SAS e SPSS).
- Edições históricas: 1995, 1997, 1999, 2001, 2003, 2005, 2011, 2013, 2015, 2017, 2019 (e posteriormente 2021, 2023 conforme páginas mais recentes do INEP).
- **Não confirmei diretamente**, nesta rodada, se o SAEB usa vírgula ou pipe como delimitador (a busca indicou vírgula, diferente do padrão pipe do Censo Escolar/ENEM) — **fica como lacuna**, precisa confirmação por leitura do Leia-Me real.

### 5. Portais estaduais/municipais — são espelhos, não fontes independentes de granularidade

- Testado: Dados Abertos SP (dadosabertos.des.sp.gov.br), dataset "Microdados do Censo Escolar" — o recurso listado ("Microdados Censo Escolar 1995-2021") aponta de volta para o portal nacional do INEP como fonte primária, e a página informa explicitamente **"Nenhuma Licença Fornecida"**. Não há evidência de granularidade adicional (ex.: nível de aluno da rede estadual) própria de SP nesse dataset — é essencialmente um espelho/catálogo apontando para o INEP.
- **Não testei outros portais estaduais/municipais** (ex. SEDU-ES) nesta rodada — permanece lacuna/pista para rodada futura.

### 6. Sedap — guia do usuário (fetch falhou; apenas resumo de busca)

- O fetch direto ao PDF do guia (https://download.inep.gov.br/dados/sedap/documentos/guia_usuario_servico_acesso_dados_protegidos_sedap.pdf) falhou por erro de conexão (ECONNRESET) — não li o conteúdo integral.
- Pela busca (não primária): o Sedap "permite acesso controlado e restrito a bases de dados protegidas... para realização de estatísticas, estudos e pesquisas científicas ou institucionais de interesse público", com salvaguardas contra vazamento e uso indevido. É a via formal citada também no RIPD dos Censos da Educação para acesso a variáveis não disponíveis no microdado público (ex.: possivelmente CPF mascarado, nível de aluno completo, variáveis suprimidas). **O processo de submissão de projeto de pesquisa não foi detalhado nesta rodada** — fica como lacuna.

## claims (resumo estruturado — ver também objeto de saída)

Ver lista formal no retorno estruturado.

## Gaps que permanecem após esta rodada

1. Não confirmei se o delimitador do SAEB é vírgula (CSV padrão) ou pipe, nem li o "Leia-Me" oficial de um pacote de microdados real (Censo Escolar ou SAEB).
2. Não reconciliei a afirmação do RIPD dos Censos da Educação de que o "novo modelo" de microdados públicos do Censo Escolar é **agregado por escola** (não por aluno) com outras fontes que descrevem arquivos "ALUNOS" no pacote de microdados — é preciso baixar um arquivo real (2023-2025) e contar linhas/verificar se há CO_ALUNO ou identificador de registro por aluno.
3. Não consegui ler o guia do usuário do Sedap (fetch falhou por erro de conexão) nem o processo de submissão de projeto de pesquisa.
4. Não investiguei portais estaduais/municipais além de São Paulo (ex. SEDU-ES) — não sei se algum oferece granularidade própria além do espelho do INEP.
5. Não obtive números de tamanho/estrutura de arquivo do Censo Escolar (apenas do ENEM: 1,4 GB, 3.389.832 registros, 2021). Não achei o equivalente "Notas Estatísticas do Censo Escolar 2025" nem RIPD com números de GB/linhas do Censo Escolar.
6. Não pesquisei Enade/Encceja (mencionados de passagem na página oficial do INEP como também tendo microdados públicos).
7. Não obtive nenhum número estatístico de calibração (evasão, notas, frequência) — fora do escopo desta dimensão, conforme instrução.
8. Não confirmei a licença exata aplicável aos arquivos de microdados em si (só a licença genérica do portal gov.br).

## Leads para próxima rodada

- Baixar um arquivo real de microdados do Censo Escolar 2023 ou 2024 (ex. via dados.gov.br ou portal INEP) e inspecionar diretamente: delimitador, presença de identificador por aluno, contagem de linhas vs. número de escolas — para resolver o gap #2 acima.
- Ler a Nota Técnica nº 12/2023-CGF/ANPD/INEP (mencionada na Rodada 1) para ver se ela revisa/atualiza a posição do RIPD de dez/2022 sobre agregação por escola.
- Tentar novamente o guia do usuário do Sedap via curl+pdftotext (a técnica que funcionou para os RIPDs nesta rodada, contornando bloqueios de WebFetch/SSL).
- Pesquisar RIPD ou nota técnica equivalente específica do SAEB (o achado desta rodada só cobriu ENEM e "Censos da Educação" — Censo Escolar + Censo da Educação Superior — não achei um RIPD dedicado ao SAEB).
- Investigar Enade e Encceja como bases adicionais com microdados públicos citadas na página oficial do INEP.
- Investigar QEdu.org.br como agregador (IDEB/SAEB/Censo Escolar) — não explorado nesta rodada, mas é fonte secundária útil para visualizar distribuições antes de buscar o dado primário.
- Checar outros portais estaduais (SEDU-ES, dados.gov.br filtrado por educação) para confirmar se algum vai além do espelho do INEP.
- Buscar diretamente os números de referência para calibração (evasão, distorção idade-série, notas SAEB, frequência) nas Notas Estatísticas do Censo Escolar e nos relatórios de resultados do SAEB — não coberto nesta rodada (fora do escopo "acesso e formato").

## Fontes consultadas nesta rodada

Ver lista formal no retorno estruturado (`sources`).
