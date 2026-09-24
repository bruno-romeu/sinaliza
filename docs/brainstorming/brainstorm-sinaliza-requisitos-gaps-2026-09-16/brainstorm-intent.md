# Sinaliza — Intenção de Brainstorm (Requisitos e Gaps)

Sinaliza é um sistema de alerta precoce de evasão escolar, projeto de TCC (ULBRA). Este documento refina requisitos dentro do escopo já entregue e avaliado pela banca — **Proposta_Sinaliza.pdf** e **Levantamento_Requisitos_Sinaliza.pdf**. Ele fecha lacunas apontadas no parecer do professor (limiares de detecção, privacidade/LGPD, origem dos dados, fronteira do score, NFRs, split de dataset), mas **não substitui nem contradiz** esses documentos aprovados. Qualquer decisão aqui é um refinamento sob o guarda-chuva do que já foi validado; nomenclaturas e escopo já aprovados (ex.: perfil "Coordenação Pedagógica") devem ser preservados, no máximo com notas de esclarecimento nos próximos artefatos (PRD/arquitetura), nunca reabrindo o documento avaliado.

## Decisões confirmadas

### Modelo de sinal e detecção
- A "mudança relevante" na trajetória do aluno é uma **convergência de sinais independentes** (uso correto dos registros de texto do professor, queda de produtividade em notas/entregas, frequência) avaliados sempre em conjunto — nunca isolados e nunca por fórmula única. O texto pedagógico entra como sinal de peso igual, não apenas como evidência passiva.
- Modelo de gravidade em camadas: um sinal isolado é apenas um "fator preocupante" (leve) e fica silencioso na linha do tempo do estudante, servindo de ponto de partida retrospectivo caso o quadro evolua. Ele só sobe para "mudanças recentes" na home quando confirma, persiste ou converge com outro sinal.
- Detecção de mudança (regra/janela/limiar) e o modelo de ML experimental são **pipelines desacoplados por design** — tornar o limiar configurável no futuro não afeta o treino do modelo.

### Janela de tempo e limiares
- O **bimestre** é a unidade natural de janela de análise; o tamanho exato do limiar será calibrado depois que a base sintética existir.
- **Limiares fixos no MVP** (não configuráveis). Configurabilidade é uma ideia para um produto real futuro, fora do escopo atual — o objetivo agora é o mínimo viável avaliável no TCC.

### Perfil de usuário
- Perfil único mantido: "Coordenação Pedagógica" e "professor" são o **mesmo perfil funcional** no MVP, com as mesmas atribuições (lançar notas, chamada, observações). Evitar a nomenclatura "professor" para não gerar confusão.
- Manter o nome oficial já aprovado **"Coordenação Pedagógica"**; apenas acrescentar, nos próximos artefatos (PRD/arquitetura), uma nota de esclarecimento sobre as atribuições acumuladas — sem reabrir o documento de requisitos já avaliado.
- ULBRA é a instituição de ensino do autor (contexto do TCC), não o alvo de implantação do produto; o projeto é uma proposta acadêmica e não vai para produção real.

### Origem dos dados
- Duas origens de dados no MVP: (1) volume histórico via **dataset sintético**, calibrado com referência estatística a uma base pública de dados educacionais da web; (2) lançamento manual pelo perfil único para novos registros a partir do uso do sistema.
- Distinção importante: a base pública é usada **apenas como referência de calibração estatística** — os registros no banco continuam 100% fictícios, nunca misturados com dado real (regra já registrada no AGENTS.md do projeto).

### Split de dataset (treino/avaliação/demo de ML)
- **Dois recortes**, não três: (1) um conjunto de **treino** do modelo de ML, nunca visto na demo/avaliação; (2) um único conjunto de **avaliação e operação/demo**, com trajetória completa e desfecho conhecido para métricas, mas truncado em "hoje" pela camada de aplicação quando usado na demo.
- Motivo: evita treinar e avaliar no mesmo conjunto (vazamento de treino) e evita vazar informação de "futuro" durante a demonstração ao vivo.

### Privacidade e acesso
- Acesso ao registro pedagógico do aluno restrito a quem abriu o acompanhamento e à coordenação. Acesso do responsável legal é aberto apenas quando legalmente necessário.
- Dados ficam retidos no banco e podem alimentar o ML.
- Exportação de relatório em caso de transferência escolar é uma **intenção de design para um cenário de produto real futuro**, não escopo de implementação do MVP/TCC — para a proposta acadêmica, documentação da intenção já é suficiente.
- Essas respostas fecham o pedido de privacidade do parecer (acesso, retenção, portabilidade) como **requisito documentado**, sem precisar virar funcionalidade agora.

### Fronteira de visibilidade do score
- O score de risco **nunca é exibido** ao usuário (nem como ranking, KPI ou dashboard de risco). Motivação central: não tratar o aluno como produto/ativo/número de dashboard.
- Fatos que bastam para a interface (já cobertos pelos documentos aprovados): linha do tempo, evidências, registros, mudanças recentes, acompanhamentos — nunca ranking/score/KPI de risco.
- Tom-alvo da experiência: "curiosidade responsável", não alarme ou urgência. Acertar esse tom evita fadiga de alarme e constrói confiança de longo prazo.
- Maior risco a evitar: o sistema parecer um "asset a se perder", no estilo CRM/alerta de churn de cliente — isso colide diretamente com a proibição já escrita no AGENTS.md (não ser CRM/painel financeiro/asset management/ranking).

### Conceito de visualização
- Metáfora aceita como princípio guia de visualização (a ser desenvolvida na etapa de UX): **curva de crescimento pediátrico** — compara o aluno sempre contra o próprio histórico, nunca entre alunos. Informativo, não alarmante.

### Arquitetura / NFRs
- Restrições reais de projeto: stack fixa (PostgreSQL/FastAPI/React/Scikit-Learn, escolhida por domínio pessoal do autor e maturidade de mercado), hospedagem gratuita sem cron, prazo final de entrega 23/11/2026 23:59 (sistema completo, hospedado, funcionando). Isso reforça o foco no mínimo viável.
- "Sem cron" é um NFR já aprovado e vira decisão de arquitetura: cálculo de trajetória/detecção deve ser **sob demanda (query-time)**, não em lote agendado.
- NFRs adicionais (acessibilidade, manutenibilidade, compatibilidade, integridade) ficam a cargo da proposta técnica subsequente (arquitetura/PRD); o usuário não tinha mais a acrescentar sobre eles nesta sessão.

## Escopo priorizado (MoSCoW)

**Must**
- Modelo de sinal em camadas (convergência de sinais, gravidade progressiva)
- Janela por bimestre com limiar fixo
- Perfil único (Coordenação Pedagógica) com nota de atribuições acumuladas
- Split de dataset treino / avaliação-operação (dois recortes)
- Privacidade documentada (acesso, retenção, uso em ML)
- Score nunca exibido + metáfora de curva de crescimento
- Cálculo de trajetória/detecção sob demanda (query-time, sem cron)
- NFRs propostos pelo coach: acessibilidade, manutenibilidade, compatibilidade, integridade

**Should**
- Log de acesso aos registros
- Método de geração do dataset sintético documentado
- Casos de teste com trajetórias conhecidas (para validar detecção)

**Could**
- Limiares configuráveis (visão de produto real futuro)
- Exportação de dados em caso de transferência escolar
- Tela técnica de visualização do score (uso interno/pesquisa)

**Em aberto** (ver seção seguinte)
- Hospedagem gratuita e cold-start
- Quem vê o score tecnicamente

## Questões em aberto

Estes itens foram deliberadamente adiados nesta sessão e **não devem ser assumidos como resolvidos** pelas próximas etapas (PRD/arquitetura/product brief) — precisam de decisão explícita depois:

- **Hospedagem gratuita vs. cold-start**: qual serviço de hospedagem gratuita usar e como reconciliar o cold-start típico desses serviços com o NFR já aprovado de resposta em até 5 segundos. Deixado em aberto por decisão do usuário, não é para ser definido agora.
- **Quem vê o score tecnicamente**: se/como o score de risco (nunca exposto ao usuário final) fica visível para fins de pesquisa/avaliação acadêmica (ex.: pesquisador, banca). Prioridade baixa, mas ainda sem resposta.

## Princípio transversal

Um único princípio ético/técnico atravessa três decisões aparentemente distintas da sessão e deve ser tratado como o princípio de design mais citável do projeto: **comparar o aluno sempre contra o próprio histórico, nunca contra os colegas**. Ele nasceu como o "fato bruto" no exercício de First Principles (sinais avaliados em conjunto, sobre a trajetória individual do aluno), reapareceu na lógica do limiar de detecção (bimestre comparado contra bimestres anteriores do mesmo aluno, não contra a turma) e voltou a aparecer, sem planejamento deliberado, na metáfora de visualização escolhida (curva de crescimento pediátrico, que também compara a criança só contra sua própria curva). Downstream, isso significa que qualquer forma de ranking, comparação entre alunos, ou benchmarking coletivo é incompatível com o produto — o dado individual do aluno é sempre a única referência válida para ele mesmo.
