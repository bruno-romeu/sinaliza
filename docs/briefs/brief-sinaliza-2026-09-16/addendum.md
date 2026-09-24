# Addendum — Sinaliza Product Brief

Material que aprofunda o brief, ou que é relevante para etapas futuras (PRD, arquitetura, UX), mas não cabe no documento executivo. Nada aqui contradiz a Proposta ou o Levantamento de Requisitos já aprovados — é detalhe de apoio às decisões já tomadas em brainstorming.

## Por que perfil único, e não "professor" + "coordenação"

O Levantamento de Requisitos já aprovado define um único perfil: Coordenação Pedagógica. Durante o refinamento, surgiu a tentação de nomear um segundo perfil "professor" para refletir quem de fato lança chamada/nota/entrega no dia a dia. Essa alternativa foi conscientemente rejeitada: criar um segundo perfil reabriria o documento de requisitos já avaliado pela banca. Além disso, a frase "quem abriu o acompanhamento" (usada durante o brainstorm) só faria sentido se existissem múltiplos usuários *dentro* do mesmo perfil, com escopo de acesso por registro — não múltiplos perfis com atribuições diferentes. A decisão final mantém o nome oficial "Coordenação Pedagógica" para o perfil único, com as mesmas atribuições descritas no README (lançar chamada, nota, entrega, observação, revisar evidências, abrir/conduzir acompanhamentos). O termo "professor" deve ser evitado na nomenclatura de produto e de código para não sugerir um segundo perfil inexistente. Isso é uma nota de esclarecimento a incluir no PRD/arquitetura, nunca uma reabertura do documento avaliado.

## Geração do dataset sintético

Já registrado como regra no AGENTS.md e no README, vale reforçar aqui como insumo para arquitetura/PRD:

- Gerador determinístico, com seed fixa, documentado e testável.
- Cada perfil sintético tem regra conhecida (ex.: `profile = falling_attendance`), nunca geração aleatória opaca.
- Metadados da geração são persistidos.
- Escala sugerida: ~200 estudantes fictícios, um ano letivo, múltiplos períodos, observações qualitativas sintéticas, com "ground truth" dos padrões usados na geração.
- Perfis sintéticos previstos: estável, dificuldade acadêmica, queda de frequência, aumento de atividades pendentes, deterioração combinada, alta ausência com notas estáveis, mudança temporária seguida de recuperação.
- Referência estatística a uma base pública de dados educacionais da web é usada **apenas para calibração** dos parâmetros de geração — nunca misturada ao banco, que permanece 100% fictício.

## Split de dataset — detalhe do raciocínio

Dois recortes, não três:

1. **Treino**: usado só para ajustar o modelo de ML; nunca aparece na demo ou na avaliação de métricas.
2. **Avaliação/operação/demo**: um único conjunto, com trajetória completa e desfecho conhecido (para calcular precision/recall/F1/matriz de confusão), mas truncado em "hoje" pela camada de aplicação quando usado ao vivo na demonstração.

Motivo de usar um único conjunto para avaliação e demo (em vez de três recortes separados): evita treinar e avaliar no mesmo conjunto (vazamento de treino) e evita vazar informação de "futuro" durante a apresentação ao vivo, sem precisar manter três bases sintéticas sincronizadas.

## Metáfora de visualização — curva de crescimento pediátrico

Aceita como princípio guia para a etapa de UX, ainda não desenhada em detalhe: a visualização de trajetória do estudante deve comparar sempre o aluno contra seu próprio histórico, nunca contra outros alunos — a mesma lógica do gráfico de crescimento pediátrico já descrita no princípio transversal do brief. O que este addendum acrescenta é o tom-alvo dessa visualização: informativo, não alarmante, reforçando a "curiosidade responsável" (não alarme/urgência) definida na sessão de brainstorming. Desenvolver esse conceito visual em detalhe é trabalho da etapa de UX (`bmad-ux`), não deste brief.

## MoSCoW completo (fonte: brainstorm-intent.md)

O corpo do brief já lista Must/Should/Could/Fora de escopo de forma resumida. Registro aqui a formulação original completa da sessão de brainstorming, para rastreabilidade:

**Must**: modelo de sinal em camadas (convergência de sinais, gravidade progressiva); janela por bimestre com limiar fixo; perfil único (Coordenação Pedagógica) com nota de atribuições acumuladas; split de dataset treino/avaliação-operação (dois recortes); privacidade documentada (acesso, retenção, uso em ML); score nunca exibido + metáfora de curva de crescimento; cálculo de trajetória/detecção sob demanda (query-time, sem cron); NFRs propostos pelo coach (acessibilidade, manutenibilidade, compatibilidade, integridade).

**Should**: log de acesso aos registros; método de geração do dataset sintético documentado; casos de teste com trajetórias conhecidas (para validar detecção).

**Could**: limiares configuráveis (visão de produto real futuro); exportação de dados em caso de transferência escolar; tela técnica de visualização do score (uso interno/pesquisa).

## Requisitos funcionais e não-funcionais detalhados

A lista completa e literal de requisitos funcionais e não-funcionais já está registrada e aprovada em `docs/ulbra-models/Levantamento_Requisitos_Sinaliza.pdf`. Este brief resume os pontos relevantes ao planejamento de produto, mas o documento aprovado é a fonte de verdade para redação de épicos/histórias — nenhuma reinterpretação deste brief deve divergir do texto literal daquele documento.

## Questões em aberto — contexto adicional

- **Hospedagem gratuita vs. cold-start**: o NFR de resposta em até 5 segundos já está aprovado; o que falta é escolher o serviço de hospedagem gratuita e desenhar a estratégia de arquitetura (ex.: warm-up, cache, tamanho de instância) que reconcilie cold-start típico desses serviços com esse NFR. Decisão adiada para a etapa de arquitetura.
- **Quem vê o score tecnicamente**: prioridade baixa. A pergunta é se/como o score de risco — nunca exposto ao usuário final do produto — deve ficar visível para fins de pesquisa/avaliação acadêmica (ex.: tela técnica restrita, anexo de avaliação, notebook separado). Não decidir isso implicitamente ao implementar a "tela técnica de visualização do score" (item Could) sem revisitar a pergunta.
