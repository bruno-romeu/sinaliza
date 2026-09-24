---
title: "PRD: Sinaliza"
status: final
created: 2026-09-16
updated: 2026-09-23
---

# PRD: Sinaliza — Sistema de Apoio ao Acompanhamento da Trajetória Escolar

> Este PRD refina, e não substitui, a **Proposta** e o **Levantamento de Requisitos** já entregues e avaliados pela banca ULBRA (`docs/ulbra-models/`). Todos os requisitos aprovados naquele documento estão preservados aqui, renumerados, sem reinterpretação de texto ou de escopo. Os itens marcados **[NOVO]** fecham lacunas apontadas no parecer do professor (limiares de detecção, privacidade, origem dos dados, fronteira do score experimental, NFRs de acessibilidade/manutenibilidade/compatibilidade/integridade) e foram decididos em sessão de brainstorming dedicada (`docs/brainstorming/brainstorm-sinaliza-requisitos-gaps-2026-09-16/`). Nenhum item novo contradiz ou reabre o que já foi avaliado.

## 0. Propósito do Documento

Este PRD é o documento de planejamento de produto do Sinaliza, projeto de TCC (Curso Superior de Tecnologia em Análise e Desenvolvimento de Sistemas, ULBRA). Destina-se ao próprio autor (que acumula os papéis de PM, arquiteto e desenvolvedor) como base para as etapas seguintes — arquitetura, UX, épicos/histórias — e à banca avaliadora como evidência de que os gaps do parecer foram tratados sem reabrir o que já foi aprovado. Estrutura: vocabulário fixado no Glossário (§3), requisitos funcionais numerados globalmente como **RF-N** e agrupados por funcionalidade (§4), requisitos não funcionais numerados globalmente como **RNF-N** (§7), suposições marcadas inline com `[ASSUMPTION]` e indexadas (§10). Este PRD constrói sobre o Product Brief (`docs/briefs/brief-sinaliza-2026-09-16/brief.md` + `addendum.md`) e não duplica seu conteúdo narrativo — remete a ele onde fizer sentido.

## 1. Visão

Sinaliza é um sistema web de apoio ao acompanhamento pedagógico da trajetória escolar. Ele reúne frequência, notas, atividades entregues e registros pedagógicos em texto livre para responder a uma pergunta diferente da que a maioria dos sistemas de evasão escolar tenta responder: não "qual aluno tem mais risco", mas **o que mudou recentemente na trajetória deste estudante, e por que isso merece atenção da equipe pedagógica**.

O sistema calcula indicadores de trajetória em janela rolante, detecta mudanças relevantes por convergência de sinais — nunca por um único indicador isolado ou fórmula única — e sempre aponta para os registros de origem que sustentam cada mudança. A partir dessas evidências, a coordenação pedagógica abre e conduz acompanhamentos até sua conclusão. Um modelo de Machine Learning, treinado sobre dataset sintético, explora de forma experimental se é possível reconhecer padrões associados à evasão — sempre tratado como resultado de pesquisa, nunca como fato ou probabilidade real sobre o estudante.

Soluções de mercado para esse tipo de problema costumam resolver isso calculando um score de risco e gerando um ranking dos alunos mais críticos — abordagem que rotula o aluno e o aproxima, na prática, de um CRM de churn de clientes. Esse é exatamente o risco que este projeto se propõe a evitar (RF-21, §5): o produto nunca deve parecer um "asset a se perder".

Um único princípio ético e técnico atravessa as decisões mais importantes do produto: **o aluno é sempre comparado contra o próprio histórico, nunca contra os colegas** — na definição de mudança relevante, no limiar de detecção e na metáfora de visualização (curva de crescimento pediátrico, a desenvolver na etapa de UX). Por ser um projeto acadêmico, todos os dados são sintéticos e o sistema não é destinado a implantação em escola real.

## 2. Usuário-Alvo

### 2.1 Perfil de Usuário

**Coordenação Pedagógica** é o único perfil de usuário do sistema — conforme já aprovado no Levantamento de Requisitos (RF-02). `[NOTE FOR PM]` Nota de esclarecimento, sem reabrir o documento avaliado: na prática de uso, esse perfil acumula as atribuições que normalmente seriam de um professor de rotina (lançar chamada, notas, entregas de atividades e observações pedagógicas) além das atribuições de coordenação propriamente ditas (revisar evidências, abrir e conduzir acompanhamentos). O termo **"professor" deve ser evitado** na nomenclatura de produto e de código, para não sugerir um segundo perfil que não existe (ver `addendum.md` do brief para o raciocínio completo).

### 2.2 Jobs To Be Done

- Perceber cedo, com evidência, quando a trajetória de um estudante muda de padrão — sem precisar cruzar manualmente chamada, diário de classe, notas e anotações soltas.
- Ter um lugar único para registrar o que já observa na rotina (chamada, nota, entrega, observação pedagógica), sem esforço extra de preencher classificações subjetivas como "nível de risco" ou "engajamento".
- Abrir, conduzir e encerrar um acompanhamento com base em evidência rastreável até o dado-fonte, nunca em uma afirmação solta de risco.

### 2.3 Fora do Escopo de Usuários (v1)

- Professores como perfil separado da coordenação (ver §2.1).
- Responsável legal do estudante como usuário do sistema — acesso previsto apenas quando legalmente necessário, fora do MVP (ver RNF-12).
- Secretaria de educação, gestão de rede ou qualquer outro sistema educacional real (fora de escopo, ver §6.2).

### 2.4 Jornadas-Chave do Usuário

- **UJ-1. A coordenação percebe uma mudança convergente na home.** A coordenação pedagógica, ao abrir o sistema no início do dia, autenticada, vê a página inicial (RF-18) com a lista de mudanças recentes e acompanhamentos em andamento. Uma linha mostra um estudante cuja frequência caiu e cujas atividades entregues diminuíram no mesmo bimestre (RF-11). Ela abre a trajetória do estudante (RF-19), revisa a linha do tempo com as evidências apontadas (registros de origem — RF-09), e decide abrir um acompanhamento (RF-12). **Resolução:** o acompanhamento passa a existir com status "em observação", vinculado às evidências que o justificaram.
- **UJ-2. A coordenação registra uma observação pedagógica no dia a dia.** Durante a rotina de aula, a coordenação (no papel acumulado de professor) registra uma observação em texto livre sobre um estudante (RF-08) — um fato observável, não uma classificação subjetiva. O registro fica disponível como evidência potencial para futuras mudanças de trajetória detectadas para aquele estudante.
- **UJ-3. A coordenação conduz um acompanhamento até o encerramento.** A coordenação abre a tela de um acompanhamento ativo (RF-20), registra uma ação tomada, e depois de observar recuperação nos sinais do estudante, altera o status para "encerrado" (RF-13). O histórico completo de ações e evidências permanece acessível (RF-14).

*Escopo mais leve que o padrão de PRD, compatível com projeto de TCC de autor único: as três jornadas cobrem o ciclo completo evidência → acompanhamento → decisão humana; não há múltiplos perfis ou dispositivos a mapear.*

## 3. Glossário

*Termos sem marcação vêm do Levantamento de Requisitos aprovado. Termos com **[NOVO]** foram cunhados no refinamento em brainstorming (`brainstorm-intent.md`) e não substituem nem contradizem vocabulário aprovado.*

- **Coordenação Pedagógica** — único perfil de usuário do sistema. Acumula lançamento de rotina (chamada, nota, entrega, observação) e condução de acompanhamento. Nunca chamado de "professor" no produto.
- **Registro Pedagógico** — observação em texto livre feita pela coordenação sobre um estudante (RF-08).
- **Trajetória** — evolução temporal dos indicadores de um estudante (frequência, notas, atividades pendentes), calculada em janela rolante (RF-10).
- **Mudança Relevante (Trajectory Change)** — alteração de padrão detectada por **convergência de sinais independentes** (frequência, desempenho, atividades, registro pedagógico), nunca por um sinal isolado ou fórmula única. Sempre referencia os registros de origem que a sustentam (RF-11, RF-09).
- **Fator Preocupante** **[NOVO]** — sinal isolado que ainda não convergiu, confirmou ou persistiu; fica silencioso na linha do tempo do estudante como ponto de partida retrospectivo, sem subir às "mudanças recentes" da home.
- **Acompanhamento (Follow-Up)** — processo humano aberto pela coordenação para um estudante, com estados `em observação`, `ativo`, `aguardando retorno`, `encerrado` (RF-12, RF-13). Nunca um estado `HIGH_RISK` ou equivalente.
- **Score Experimental** — saída numérica do modelo de ML, associada a padrões de evasão no dataset sintético. Nunca exibido ao usuário final, nunca tratado como fato ou probabilidade real (RF-16, RF-17, RNF-14).
- **Dataset Sintético** — base de dados fictícia gerada deterministicamente, usada como origem de volume histórico. Ver RNF-13.
- **Recorte de Treino** **[NOVO]** — parte do dataset sintético usada exclusivamente para ajustar o modelo de ML; nunca aparece na avaliação ou na demonstração (RF-23).
- **Recorte de Avaliação/Operação/Demo** **[NOVO]** — parte do dataset sintético com trajetória completa e desfecho conhecido, usada para métricas de ML e para a demonstração ao vivo (truncada em "hoje" pela aplicação) (RF-23).
- **Bimestre** **[NOVO]** — unidade natural de janela de análise para detecção de mudança de trajetória, com limiar fixo no MVP (RF-11).

## 4. Funcionalidades

### 4.1 Autenticação e Acesso

**Descrição:** Acesso ao sistema restrito a usuários autenticados, perfil único.

**Requisitos Funcionais:**

#### RF-01: Autenticação obrigatória
O sistema deve exigir autenticação (login e senha) para acesso.

#### RF-02: Perfil único
O sistema possui um único perfil de usuário: Coordenação Pedagógica.

### 4.2 Frequência

**Requisitos Funcionais:**

#### RF-03: Registro de presença/falta
O sistema deve registrar presença ou falta de cada estudante por data e turma.

**[NOTE FOR PM]** O Levantamento de Requisitos aprovado não especifica se uma falta exige código de justificativa (justificada vs. não justificada). Fica como decisão de arquitetura/modelo de dados a definir — afeta como RF-11 computa "queda de frequência" (contar toda falta igualmente ou diferenciar por justificativa).

#### RF-04: Impedir duplicidade de registro
O sistema deve impedir duplicidade de registro de presença para o mesmo estudante, turma e data.

### 4.3 Notas

**Requisitos Funcionais:**

#### RF-05: Registro de notas
O sistema deve registrar notas de estudantes por disciplina e período letivo.

**[NOTE FOR PM]** O Levantamento de Requisitos aprovado não especifica escala/faixa de nota (ex.: 0–10, 0–100, conceito) nem semântica de aprovação/reprovação. Fica como decisão de arquitetura/modelo de dados a definir (ver `docs/data-model.md`), sem impacto no requisito aprovado em si.

### 4.4 Atividades

**Requisitos Funcionais:**

#### RF-06: Cadastro de atividades
O sistema deve cadastrar atividades vinculadas a turma, disciplina e período letivo.

#### RF-07: Status de entrega
O sistema deve registrar o status de entrega de cada estudante para uma atividade (entregue, não entregue ou parcial).

### 4.5 Registros Pedagógicos

**Requisitos Funcionais:**

#### RF-08: Observações em texto livre
O sistema deve registrar observações em texto livre sobre um estudante.

#### RF-09: Referência ao registro original
O sistema deve manter a referência ao registro original em qualquer sinal derivado dele.

### 4.6 Trajetória

**Descrição:** Núcleo do produto — indicadores calculados em janela rolante e detecção de mudança por convergência de sinais. Realiza UJ-1.

**Requisitos Funcionais:**

#### RF-10: Cálculo de indicadores de trajetória
O sistema deve calcular indicadores de trajetória do estudante (frequência, notas, atividades pendentes) em uma janela de tempo rolante.

#### RF-11: Detecção de mudança relevante
O sistema deve detectar mudanças relevantes na trajetória, como queda de frequência, queda de desempenho ou aumento de atividades não entregues, sempre referenciando os registros que as sustentam.

**Consequências (testáveis) — refinamento do brainstorming, não texto literal do Levantamento de Requisitos aprovado [NOVO]:**
- Uma mudança relevante nunca é gerada por um único sinal isolado ou fórmula única — exige convergência de sinais independentes. `[ASSUMPTION: "convergência" é operacionalizada na arquitetura como confirmação, persistência ou coincidência de ao menos dois sinais independentes no mesmo bimestre; o limiar exato é fixo no MVP e calibrado quando a base sintética existir (ver Open Questions / addendum do brief).]`
- Um registro pedagógico em texto conta como sinal independente com peso igual aos demais (frequência, desempenho, atividades) — não apenas como evidência de apoio a um sinal numérico; pode, por si só, contribuir para a convergência que caracteriza uma mudança relevante.
- O bimestre é a unidade natural de janela usada para o limiar de detecção; a granularidade rolante (`window_days`) de frequência/atividades é tratada na camada de arquitetura (ver `docs/data-model.md`), sem contradizer este requisito.
- Um sinal isolado que não confirma, persiste ou converge fica registrado como "fator preocupante" na trajetória do estudante, sem subir à lista de mudanças recentes da home (RF-18).
- Todo `TrajectoryChange` exibido aponta para ao menos um registro de origem (`source_record_ids`), nunca para uma afirmação solta do tipo "a IA identificou risco".

### 4.7 Acompanhamento

**Descrição:** Processo humano conduzido pela coordenação a partir das evidências reunidas. Realiza UJ-1, UJ-3.

**Requisitos Funcionais:**

#### RF-12: Abertura de acompanhamento
A coordenação pedagógica deve poder abrir um acompanhamento para um estudante.

#### RF-13: Registro de ações e mudança de status
A coordenação pedagógica deve poder registrar ações e alterar o status de um acompanhamento entre em observação, ativo, aguardando retorno ou encerrado.

#### RF-14: Histórico de ações e evidências
O sistema deve manter histórico de ações e evidências de cada acompanhamento.

### 4.8 Privacidade e Acesso a Registros **[NOVO]**

**Descrição:** Fecha o gap de privacidade apontado no parecer do professor, dentro do que já foi decidido no brainstorming (`brainstorm-intent.md`, seção "Privacidade e acesso"). Não introduz um segundo perfil de usuário — apenas escopa a visibilidade de um registro pedagógico por acompanhamento, dentro do único perfil já aprovado (Coordenação Pedagógica).

**Requisitos Funcionais:**

#### RF-22: Escopo de acesso ao registro pedagógico do estudante
O sistema deve associar um usuário responsável a cada acompanhamento e restringir a visibilidade do registro pedagógico do estudante vinculado a esse acompanhamento ao usuário responsável e à coordenação pedagógica.

**Consequências (testáveis):**
- Todo `FollowUp` tem um `responsible_user_id` (já previsto em `docs/data-model.md`).
- Esta restrição é estrutural (preparação para crescimento futuro do sistema), não uma barreira entre "papéis" diferentes — hoje há um único perfil, então na prática todo usuário autenticado é coordenação pedagógica.

**Out of Scope:**
- Acesso do responsável legal do estudante ao registro pedagógico — previsto apenas para quando for legalmente necessário; não é funcionalidade a implementar no MVP (ver RNF-12).

### 4.9 Machine Learning (Experimental)

**Descrição:** Pipeline desacoplado por design da regra de detecção de mudança (RF-11) — tornar o limiar de detecção configurável no futuro não afeta o treino do modelo, e vice-versa.

**Requisitos Funcionais:**

#### RF-15: Geração de score experimental
O sistema deve gerar, a partir do dataset sintético, um score experimental associado a padrões de evasão.

#### RF-16: Score como dado experimental
Esse score deve ser tratado sempre como dado experimental, nunca como fato ou probabilidade real.

#### RF-17: Versionamento do modelo
O sistema deve versionar o modelo utilizado e associar cada predição à sua versão.

#### RF-23: Split de dataset em dois recortes **[NOVO]**
O pipeline de ML deve ser treinado com um recorte de dados (Recorte de Treino) nunca exposto na avaliação de métricas nem na demonstração, e avaliado/demonstrado com um segundo recorte (Recorte de Avaliação/Operação/Demo) de trajetória completa e desfecho conhecido, truncado em "hoje" pela camada de aplicação quando usado ao vivo.

**Consequências (testáveis):**
- Exatamente dois recortes existem — nunca três bases sintéticas separadas para treino/avaliação/demo.
- O recorte de avaliação/operação/demo é o mesmo conjunto usado para calcular precision/recall/F1/matriz de confusão (RNF-14) e para a demonstração ao vivo; a diferença entre os dois usos é a truncagem em "hoje", aplicada na camada de aplicação, não no dado persistido.
- Nenhum registro do recorte de treino aparece na avaliação de métricas ou na demonstração (evita vazamento de treino).
- Nenhuma informação posterior a "hoje" (na trajetória truncada) fica visível durante uma demonstração ao vivo (evita vazamento de futuro).

### 4.10 Interface

**Requisitos Funcionais:**

#### RF-18: Página inicial
O sistema deve exibir uma página inicial com mudanças recentes e acompanhamentos em andamento.

#### RF-19: Trajetória do estudante
O sistema deve exibir a trajetória do estudante, com linha do tempo, evidências e registros.

#### RF-20: Tela de acompanhamento
O sistema deve exibir uma tela de acompanhamento, com status, ações registradas e evidências vinculadas.

#### RF-21: Proibição de ranking/score/KPI de risco
A interface não deve exibir ranking de estudantes por risco, score de evasão ou KPIs do tipo "alunos de alto risco".

**Feature-specific NFRs:**
- A visualização de trajetória (RF-19) segue a metáfora de curva de crescimento pediátrico — o estudante é sempre comparado contra o próprio histórico, nunca contra colegas — a desenvolver em detalhe na etapa de UX (`bmad-ux`). Tom-alvo: "curiosidade responsável", não alarme ou urgência — acertar esse tom evita fadiga de alarme e constrói confiança de longo prazo da coordenação com o sistema.
- Nenhuma funcionalidade do sistema deve implementar comparação direta entre estudantes (ranking, percentil, benchmarking) — reforça o princípio transversal do §1 e o Não-Objetivo correspondente (§5). RF-21 cobre a proibição de score/ranking na interface; esta linha estende a mesma proibição a qualquer funcionalidade futura, não só à tela.

## 5. Não-Objetivos Explícitos

*Já definidos e fixos nos documentos aprovados (Proposta e Levantamento de Requisitos); reafirmados aqui para os leitores deste PRD:*

- Integração com secretaria de educação ou qualquer sistema educacional real.
- Dados reais de estudantes, em qualquer hipótese — o sistema opera exclusivamente com dados sintéticos (RNF-07).
- Tomada automática de decisão, comunicação automática com responsáveis, recomendação disciplinar ou diagnóstico psicológico.
- Implantação em escola real ou uso do modelo em decisão de alto impacto.
- Um segundo perfil de usuário ("professor") distinto da Coordenação Pedagógica (§2.1).
- Qualquer forma de ranking, comparação entre alunos ou benchmarking coletivo (princípio transversal, §1).

## 6. Escopo do MVP

### 6.1 Escopo (Must)

- Modelo de sinal em camadas: convergência de sinais, gravidade progressiva, nunca fórmula única (RF-11).
- Detecção por janela de bimestre com limiar fixo, não configurável no MVP (RF-11).
- Perfil único (Coordenação Pedagógica), com atribuições acumuladas documentadas (RF-02, §2.1).
- Dois recortes de dataset: treino (nunca visto na avaliação) e avaliação/operação/demo (RF-23).
- Privacidade documentada: acesso restrito a quem abriu o acompanhamento e à coordenação (RF-22); retenção e uso em ML registrados como requisito (RNF-12).
- Score de ML nunca exibido ao usuário; visualização de trajetória segue a metáfora de curva de crescimento (RF-21, RF-19).
- Cálculo de trajetória/detecção sob demanda (query-time), sem jobs agendados (RNF-06).
- NFRs de acessibilidade, manutenibilidade, compatibilidade e integridade, detalhados na arquitetura (RNF-08 a RNF-11).

### 6.2 Fora de Escopo para o MVP

- **Limiares configuráveis** — visão de produto real futuro; fora do escopo do MVP/TCC.
- **Exportação de dados em caso de transferência escolar** — intenção de design documentada (RNF-12); não é funcionalidade do MVP.
- **Tela técnica de visualização do score** — decidido (§9, item 2) que não é construída no MVP; o relatório de `python -m app.ml.evaluate` cobre a necessidade de avaliação acadêmica.
- **Log de acesso aos registros pedagógicos** *(Should)* — desejável, não essencial para o MVP avaliável.
- **Método de geração do dataset sintético documentado publicamente** *(Should)* — a geração em si é Must implícito (RNF-13); a documentação formal do método é Should.
- **Casos de teste com trajetórias sintéticas conhecidas para validar a regra de detecção** *(Should)*.
- Integração com secretaria de educação, dados reais, automação de decisão (§5).

## 7. Requisitos Não Funcionais

*Requisitos RNF-01 a RNF-07 já constam, com este texto, no Levantamento de Requisitos aprovado — preservados sem reinterpretação. RNF-08 em diante são itens novos que fecham lacunas do parecer do professor, decididos no brainstorming.*

#### RNF-01: Desempenho
O sistema deve responder às interações do usuário em no máximo 5 segundos.

#### RNF-02: Usabilidade
A interface deve ser responsiva, adaptando-se a desktop e tablet.

#### RNF-03: Confiabilidade
O pipeline de pré-processamento e inferência do modelo de Machine Learning deve ser o mesmo utilizado no treinamento.

#### RNF-04: Disponibilidade
O sistema deve estar disponível durante o ambiente de desenvolvimento e demonstração, sem exigência de disponibilidade contínua (24 horas por dia, 7 dias por semana).

#### RNF-05: Segurança
O acesso deve ser protegido por autenticação com login e senha, com senha armazenada de forma criptografada. Existe um único perfil de usuário.

#### RNF-06: Tecnologias envolvidas
PostgreSQL como banco de dados, back-end em Python com FastAPI, front-end em React/Next.js e Scikit-Learn para Machine Learning, hospedado em serviço gratuito, sem uso de jobs agendados (cron).

#### RNF-07: Dados exclusivamente sintéticos
O sistema deve operar exclusivamente com dados sintéticos; nenhuma predição de Machine Learning deve ser apresentada como fato determinístico.

---

#### RNF-08: Acessibilidade **[NOVO]**
A interface deve seguir diretrizes básicas de acessibilidade, com WCAG 2.1 nível AA como referência (não certificação formal), nas telas principais do produto: página inicial (RF-18), trajetória do estudante (RF-19) e tela de acompanhamento (RF-20).

**Consequências (testáveis):**
- Contraste mínimo de texto conforme WCAG 2.1 AA.
- Navegação completa por teclado nas três telas principais.
- Formulários de lançamento (chamada, nota, entrega, observação) com labels associados aos campos.
- Nenhuma informação de mudança de trajetória comunicada exclusivamente por cor (ver também AGENTS.md — "não usar cor vermelha como mecanismo único para classificar estudantes").

#### RNF-09: Manutenibilidade **[NOVO]**
O código deve ser organizado em camadas (domínio, aplicação, apresentação), com testes automatizados cobrindo a regra de detecção de mudança de trajetória (RF-11) e o pipeline de pré-processamento/inferência do modelo de ML (RNF-03).

**Consequências (testáveis):**
- Testes unitários cobrindo: gerador sintético, cálculo de tendência/trajetória, detecção de mudança, pipeline de pré-processamento (alinhado a AGENTS.md, seção Testes).
- Decisões técnicas relevantes (features, geração sintética, thresholds, estratégia de avaliação) documentadas em `docs/` conforme já estabelecido em AGENTS.md.

#### RNF-10: Compatibilidade **[NOVO]**
O sistema deve funcionar nas versões estáveis mais recentes dos navegadores Chrome, Firefox e Edge, nas resoluções de desktop e tablet já exigidas por RNF-02.

#### RNF-11: Integridade **[NOVO]**
O sistema deve garantir integridade referencial entre toda mudança de trajetória exibida e os registros de origem que a sustentam, e impedir estados de dado inconsistentes nos fatos observáveis.

**Consequências (testáveis):**
- Nenhum `TrajectoryChange` é exibido sem ao menos um `source_record_id` válido (reforça RF-11 e RF-09).
- Duplicidade de registro de presença para o mesmo estudante/turma/data continua impedida em nível de banco (reforça RF-04), não apenas na camada de aplicação.
- Um acompanhamento nunca é exibido com um status fora do conjunto fechado já aprovado (em observação, ativo, aguardando retorno, encerrado) — nunca um estado equivalente a "alto risco" (reforça RF-13, alinhado a AGENTS.md).

#### RNF-12: Privacidade e Retenção de Dados **[NOVO]**
Requisito documentado, sem exigência de nova funcionalidade além de RF-22 no MVP.

- O acesso ao registro pedagógico de um estudante é restrito a quem abriu o acompanhamento e à coordenação pedagógica (implementado por RF-22).
- O acesso do responsável legal do estudante ao registro pedagógico é previsto apenas quando legalmente necessário — não é fluxo a implementar no MVP.
- Os dados retidos no banco podem alimentar o treinamento do modelo de ML (RF-15); não há política de expurgo automático no MVP.
- Exportação de dados em caso de transferência escolar é uma intenção de design para um cenário de produto real futuro (ver §6.2) — documentar a intenção é suficiente para a entrega acadêmica; não é funcionalidade do MVP.
- Todo o banco de dados do projeto é 100% fictício, conforme já registrado em AGENTS.md — este requisito documenta política de acesso e retenção *sobre* esse dado fictício, não uma obrigação de proteção de dado real.

#### RNF-13: Origem e Governança dos Dados **[NOVO]**
Elabora RNF-07 sem contradizê-lo. O MVP usa duas origens de dados controladas:

1. **Dataset sintético** — gerador determinístico com seed fixa, documentado e testável; cada perfil sintético tem regra conhecida (ex.: `profile = falling_attendance`), nunca geração aleatória opaca; metadados da geração são persistidos. Calibrado por **referência estatística a uma base pública de dados educacionais** — usada apenas como referência de calibração dos parâmetros de geração, **nunca misturada ao banco do sistema**, que permanece 100% fictício.
2. **Lançamento manual** — feito pela coordenação pedagógica a partir do uso corrente do sistema (RF-03 a RF-09).

**Consequências (testáveis):**
- Nenhum dado real de estudante (nome, matrícula, telefone, endereço, observação, dado de saúde ou informação familiar real) é commitado em nenhuma hipótese (alinhado a AGENTS.md, seção Privacidade).
- A base pública usada para calibração nunca é consultada em tempo de execução do produto nem persistida no banco do sistema.

#### RNF-14: Fronteira do Score Experimental e Avaliação do ML **[NOVO]**
Elabora RF-16 e RNF-07 com o método de avaliação e o limite explícito de interpretação do score.

- A avaliação do modelo de ML usa precision, recall, F1 e matriz de confusão como métricas obrigatórias; ROC-AUC e PR-AUC são métricas adicionais.
- Os resultados devem ser documentados estritamente como **capacidade de reconhecer os padrões simulados no dataset sintético utilizado** — nunca como validade preditiva sobre uma população escolar real.
- O split de dataset (RF-23) é pré-condição desta avaliação: treino e avaliação nunca compartilham o mesmo recorte.

**Consequências (testáveis):**
- Nenhum relatório, tela ou demonstração apresenta o score ou as métricas de ML como "precisão do sistema em prever evasão escolar no mundo real" (alinhado a AGENTS.md, seção Avaliação de ML).
- Todo relatório de avaliação declara explicitamente o dataset sintético utilizado e o recorte (treino vs. avaliação/operação/demo).

## 8. Critérios de Sucesso

Como projeto de TCC, o sucesso tem duas camadas que precisam ser lidas juntas.

**Primários**
- **SM-1**: Sistema completo, hospedado e funcional até 23/11/2026 às 23:59. Valida RNF-04, RNF-06.
- **SM-2**: Toda mudança relevante detectada aponta para evidência rastreável até o dado-fonte, em 100% dos casos exibidos. Valida RF-11, RF-09, RNF-11.
- **SM-3**: Nenhuma tela do sistema exibe score, ranking ou KPI de risco em nenhum momento da demonstração. Valida RF-21.
- **SM-4**: Pipeline de ML avaliado com precision/recall/F1/matriz de confusão, documentado com a separação explícita entre "reconhece padrões simulados" e "validade preditiva real". Valida RF-16, RNF-14.

**Secundários**
- **SM-5**: A coordenação consegue abrir, conduzir e encerrar um acompanhamento completo usando apenas os dados e evidências apresentados pelo sistema, sem informação externa. Valida RF-12, RF-13, RF-14.
- **SM-6**: Toda seção deste PRD é rastreável a um item do Levantamento de Requisitos aprovado ou está marcada explicitamente como **[NOVO]**; nenhum item **[NOVO]** contradiz ou estreita um item aprovado — verificado por conferência linha a linha (RF/RNF vs. `Levantamento_Requisitos_Sinaliza.pdf`) antes da entrega final.

**Contra-métricas (não otimizar)**
- **SM-C1**: Número de sinais isolados promovidos precocemente a "mudança relevante" sem convergência, persistência ou confirmação — contrabalança SM-2 (não é para o sistema "achar" mais mudanças à custa de falsos positivos). Contrabalança SM-2.
- **SM-C2**: Complexidade do modelo de ML (número de features, comparação de algoritmos) tratada como custo, não como meta — o objetivo é honestidade experimental, não sofisticação. Contrabalança SM-4.

## 9. Questões em Aberto

Deliberadamente adiadas na sessão de brainstorming; **não devem ser assumidas como resolvidas** pelas próximas etapas (arquitetura, UX, épicos/histórias) — cada uma precisa de decisão explícita na etapa correspondente.

1. **Hospedagem gratuita vs. cold-start**: qual serviço de hospedagem gratuita usar e como reconciliar o cold-start típico desses serviços com o RNF-01 (resposta em até 5 segundos). Decisão de arquitetura.
2. ~~**Quem vê o score tecnicamente**~~ — **Decidido (2026-09-23):** nenhuma tela técnica de visualização do score é construída no MVP. O relatório gerado por `python -m app.ml.evaluate` (RF-15/RF-17, RNF-14) é o próprio artefato de avaliação acadêmica/pesquisa — nenhum boundary de leitura novo além do que a Epic 5 (`docs/epics.md`) já especifica. Razão: menor escopo, sem pipeline/tela adicional, aderente a SM-C2 (complexidade de ML tratada como custo, não como meta). O score continua nunca exposto ao usuário final (RF-16, RF-21). Registrado em `ARCHITECTURE-SPINE.md`.
3. **Log de acesso aos registros pedagógicos** *(Should, §6.2)*: se entra no MVP ou fica para depois — depende de tempo disponível até 23/11/2026.

## 10. Índice de Suposições

- §4.6 (RF-11) — `[ASSUMPTION]`: "convergência de sinais" operacionalizada como confirmação, persistência ou coincidência de ao menos dois sinais independentes no mesmo bimestre; limiar exato fixo no MVP, a calibrar quando a base sintética existir.
