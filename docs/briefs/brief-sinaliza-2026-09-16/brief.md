---
title: "Product Brief: Sinaliza"
status: draft
created: 2026-09-16
updated: 2026-09-16
---

# Product Brief: Sinaliza — Sistema de Apoio ao Acompanhamento da Trajetória Escolar

> Este brief complementa, e não substitui, a Proposta e o Levantamento de Requisitos já entregues e avaliados pela banca ULBRA. Nada aqui reabre ou contradiz o que foi aprovado; onde há refinamento, é para fechar lacunas apontadas no parecer do professor (limiares, privacidade, origem dos dados, fronteira do score, NFRs, split de dataset), decidido em sessão de brainstorming dedicada.

## Resumo Executivo

Sinaliza é um sistema web de apoio ao acompanhamento pedagógico da trajetória escolar, desenvolvido como Projeto Tecnológico do curso de Análise e Desenvolvimento de Sistemas (ULBRA). Ele reúne frequência, notas, atividades entregues e registros pedagógicos em texto livre para responder a uma pergunta diferente da que a maioria dos sistemas de evasão escolar tenta responder: não "qual aluno tem mais risco", mas **o que mudou recentemente na trajetória deste estudante, e por que isso merece atenção da equipe pedagógica**.

O sistema calcula indicadores de trajetória em janela rolante, detecta mudanças relevantes por convergência de sinais (nunca por um único indicador isolado) e sempre aponta para os registros de origem que sustentam cada mudança. A partir dessas evidências, a coordenação pedagógica abre e conduz acompanhamentos até sua conclusão. Um modelo de Machine Learning, treinado sobre dataset sintético, explora de forma experimental se é possível reconhecer padrões associados à evasão — sempre tratado como resultado de pesquisa, nunca como fato sobre o estudante ou probabilidade real.

Por ser um projeto acadêmico, todos os dados são sintéticos e o sistema não é destinado a implantação em escola real. O objetivo é demonstrar, com rigor técnico e ético, como dados que já existem na rotina escolar podem ser organizados para dar visibilidade antecipada a mudanças que merecem acompanhamento humano — sem transformar o estudante em score, ranking ou ativo a ser gerenciado.

## O Problema

A evasão escolar raramente é um evento súbito. Antes de um abandono, costumam existir sinais prévios — queda progressiva de frequência, faltas consecutivas, oscilação de desempenho, aumento de atividades não entregues, mudanças de participação percebidas pelo professor. O problema não é a ausência desses sinais: é que eles ficam **espalhados** entre chamada, diário de classe, notas, planilhas e anotações soltas da coordenação, e raramente alguém consegue reuni-los a tempo de agir.

Soluções de mercado para esse tipo de problema costumam resolver isso calculando um **score de risco** e gerando um **ranking dos alunos mais críticos**. Essa abordagem tem um custo: ela rotula o aluno, oferece pouca coisa acionável para quem está na rotina (professor, coordenação) e trata o estudante como um número em um painel — próximo, na prática, de um CRM de churn de clientes. Esse é exatamente o risco que este projeto se propõe a evitar.

## A Solução

O Sinaliza organiza os fatos que já fazem parte da rotina escolar — presença, notas, atividades, observações pedagógicas em texto livre — em uma trajetória temporal por estudante. A partir dessa trajetória, ele detecta **mudanças relevantes** e as apresenta sempre acompanhadas da evidência que as sustenta (o registro, a data, a origem), nunca como uma classificação isolada.

A "mudança relevante" é modelada como **convergência de sinais independentes** — frequência, desempenho, atividades e o próprio registro pedagógico em texto, avaliados sempre em conjunto, nunca por fórmula única ou sinal isolado. Um sinal isolado é apenas um "fator preocupante" leve, que fica silencioso na linha do tempo do aluno até confirmar, persistir ou convergir com outro sinal — só então ele sobe às "mudanças recentes" que a coordenação vê na tela inicial. A janela de análise usa o **bimestre** como unidade natural, com limiares fixos no MVP (calibração fina fica para quando a base sintética existir); o cálculo é feito sob demanda (query-time), sem depender de jobs agendados.

A partir das evidências reunidas, a coordenação pedagógica abre um acompanhamento, registra ações e conduz o processo pelos estados já aprovados (em observação, ativo, aguardando retorno, encerrado) até a conclusão. Um modelo de Machine Learning, treinado sobre dataset sintético, explora experimentalmente se é possível reconhecer padrões associados à evasão nesses dados — seu resultado é sempre dado experimental, nunca exposto como fato ou probabilidade real sobre o estudante.

## Princípio Transversal

Um único princípio ético e técnico atravessa as três decisões mais importantes do produto: **o aluno é sempre comparado contra o próprio histórico, nunca contra os colegas.** Ele aparece na definição de mudança relevante (convergência de sinais sobre a trajetória individual, nunca um ranking coletivo), no limiar de detecção (bimestre comparado contra bimestres anteriores do mesmo aluno, não contra a turma) e na metáfora de visualização adotada para a etapa de UX — a **curva de crescimento pediátrico**, que também compara a criança apenas contra sua própria curva, nunca contra outras crianças. Qualquer forma futura de ranking, comparação entre alunos ou benchmarking coletivo é incompatível com este princípio.

## O Que Torna Isso Diferente

A maioria dos sistemas de alerta de evasão escolar responde a "quem é o aluno de risco" com um score e um ranking. O Sinaliza responde a uma pergunta diferente — "o que mudou e por que merece atenção" — e isso não é só um ajuste de tom de interface, é uma escolha estrutural que atravessa modelo de dados, regra de detecção e visualização:

- **Evidência antes de classificação**: toda mudança exibida aponta para o registro-fonte; nunca existe uma afirmação solta como "a IA identificou risco alto".
- **Score nunca exibido ao usuário final**: nem como número, nem como ranking, nem como KPI de "alunos de alto risco" — decisão de princípio, não limitação técnica.
- **Decisão sempre humana**: detecção → evidências → análise pedagógica → ação humana, nunca automação de intervenção.
- **Rigor experimental honesto sobre o ML**: o modelo é avaliado pela capacidade de reconhecer padrões simulados em um dataset sintético controlado, nunca apresentado como validade preditiva sobre uma população escolar real.

## A Quem Serve

**Coordenação Pedagógica** é o único perfil de usuário do sistema (conforme já aprovado no Levantamento de Requisitos). Na prática de uso, esse perfil acumula as atribuições que normalmente seriam de um professor de rotina — lançar chamada, notas, entregas de atividades e observações pedagógicas — além das atribuições de coordenação propriamente ditas — revisar evidências, abrir e conduzir acompanhamentos. Essa nota de esclarecimento sobre atribuições acumuladas é um refinamento de artefatos futuros (PRD/arquitetura); o nome e o desenho de perfil único aprovados permanecem inalterados, e o termo "professor" deve ser evitado na nomenclatura do produto para não sugerir um segundo perfil que não existe.

O que esse usuário precisa do sistema: perceber cedo, com evidência, quando a trajetória de um estudante muda de padrão — e ter um lugar único para registrar o que já observa na rotina (chamada, nota, entrega, observação) sem esforço extra de preencher classificações subjetivas como "nível de risco" ou "engajamento".

## Escopo

**Must** (essencial para o MVP avaliável)
- Modelo de sinal em camadas: convergência de sinais, gravidade progressiva, nunca fórmula única.
- Detecção por janela de bimestre com limiar fixo (não configurável no MVP).
- Perfil único (Coordenação Pedagógica), com atribuições acumuladas documentadas.
- Dois recortes de dataset: um de treino (nunca visto na avaliação) e um de avaliação/operação/demo (trajetória completa truncada em "hoje" pela aplicação).
- Privacidade documentada: acesso restrito a quem abriu o acompanhamento e à coordenação; retenção e uso em ML registrados como requisito, mesmo sem virar funcionalidade agora.
- Score de ML nunca exibido ao usuário; visualização de trajetória segue a metáfora de curva de crescimento (a desenvolver na etapa de UX).
- Cálculo de trajetória/detecção sob demanda (query-time), sem jobs agendados.
- NFRs de acessibilidade, manutenibilidade, compatibilidade e integridade, detalhados na arquitetura.

**Should**
- Log de acesso aos registros pedagógicos.
- Documentação do método de geração do dataset sintético (determinístico, com seed, por perfil conhecido).
- Casos de teste com trajetórias conhecidas, para validar a regra de detecção.

**Could**
- Limiares configuráveis (visão de produto real futuro, fora do escopo do MVP/TCC).
- Exportação de dados em caso de transferência escolar (intenção de design documentada; não é funcionalidade do MVP).
- Tela técnica de visualização do score, para uso interno de pesquisa/avaliação acadêmica.

**Fora de escopo** (já definido nos documentos aprovados)
- Integração com secretaria de educação ou qualquer sistema educacional real.
- Dados reais de estudantes, em qualquer hipótese.
- Tomada automática de decisão, comunicação automática com responsáveis, recomendação disciplinar ou diagnóstico psicológico.
- Implantação em escola real ou uso do modelo em decisão de alto impacto.

## Dados, Privacidade e Avaliação

O MVP usa duas origens de dados: um **dataset sintético** que fornece volume histórico, calibrado por referência estatística a uma base pública de dados educacionais — apenas como referência de calibração, nunca misturado a dado real — e o **lançamento manual** feito pela coordenação a partir do uso do sistema. Todo o restante do banco permanece 100% fictício, conforme já registrado no AGENTS.md do projeto.

O acesso ao registro pedagógico de um estudante é restrito a quem abriu o acompanhamento e à coordenação; o acesso do responsável legal é previsto apenas quando legalmente necessário. Os dados ficam retidos no banco e podem alimentar o modelo de ML. Para a entrega acadêmica, essas respostas (acesso, retenção, uso em ML) já fecham o pedido de privacidade do parecer como **requisito documentado** — não é necessário implementar portabilidade ou exportação como funcionalidade agora; a exportação em caso de transferência escolar fica registrada como intenção de design para um cenário de produto real futuro.

A avaliação do modelo de ML segue a métrica já aprovada (precision, recall, F1, matriz de confusão, com ROC-AUC/PR-AUC como adicionais) e deve ser documentada estritamente como **capacidade de reconhecer os padrões simulados no dataset sintético utilizado** — nunca como validade preditiva sobre uma população escolar real. O split em dois recortes (treino nunca visto na avaliação; avaliação/operação/demo com trajetória completa, truncada em "hoje" na camada de aplicação) existe para evitar tanto o vazamento de treino quanto o vazamento de informação futura durante uma demonstração ao vivo.

## Restrições e NFRs

Estes requisitos não-funcionais já constam no Levantamento de Requisitos aprovado e são tratados como fixos:

- **Desempenho**: resposta às interações do usuário em até 5 segundos.
- **Usabilidade**: interface responsiva, adaptada a desktop e tablet.
- **Confiabilidade**: mesmo pipeline de pré-processamento usado no treinamento e na inferência do modelo de ML.
- **Disponibilidade**: sistema disponível durante desenvolvimento e demonstração, sem exigência de operação contínua 24/7.
- **Segurança**: autenticação por login e senha com hash, perfil único.
- **Stack fixa**: PostgreSQL, back-end em Python/FastAPI, front-end em React, Machine Learning em Scikit-Learn — escolhida por domínio pessoal do autor e maturidade de mercado, hospedagem em serviço gratuito, sem uso de cron.
- **Prazo**: entrega final em 23/11/2026, às 23:59 — sistema completo, hospedado e funcionando.

## Critérios de Sucesso

Como projeto de TCC, o sucesso tem duas camadas que precisam ser lidas juntas:

- **Sucesso acadêmico**: sistema completo, hospedado e funcional até 23/11/2026; documento e demonstração coerentes com a Proposta e o Levantamento de Requisitos já aprovados, sem contradição; pipeline de ML avaliado com as métricas corretas (precision/recall/F1/matriz de confusão) e documentado com a separação explícita entre "reconhece padrões simulados" e "validade preditiva real".
- **Sucesso de produto (dentro do experimento)**: uma mudança relevante detectada sempre aponta para evidência rastreável até o dado-fonte; nenhuma tela do sistema exibe score, ranking ou KPI de risco em nenhum momento da demonstração; a coordenação consegue abrir, conduzir e encerrar um acompanhamento completo usando apenas os dados e evidências apresentados pelo sistema.

## Questões em Aberto

Estas questões foram deliberadamente adiadas em sessão de brainstorming dedicada e **não devem ser assumidas como resolvidas** por PRD, arquitetura ou épicos — cada uma precisa de decisão explícita na etapa correspondente:

- **Hospedagem gratuita vs. cold-start**: qual serviço de hospedagem gratuita usar e como reconciliar o cold-start típico desses serviços com o NFR aprovado de resposta em até 5 segundos. Decisão de arquitetura, ainda em aberto.
- **Quem vê o score tecnicamente**: se e como o score de risco (nunca exposto ao usuário final do produto) fica visível para fins de pesquisa e avaliação acadêmica. Prioridade baixa, mas sem resposta ainda.
