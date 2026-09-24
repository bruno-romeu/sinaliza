# Roteiro — Vídeo de Apresentação (Etapa Proposta)

Rascunho de roteiro para o vídeo de até 3 minutos exigido na Etapa - Proposta (link obrigatório no YouTube). Pensado para ser falado, não lido decorado.

---

## [0:00–0:30] — O problema

A evasão escolar quase nunca acontece do dia pra noite. Antes de um aluno abandonar a escola, normalmente já dá pra perceber sinais: a frequência cai aos poucos, o aluno para de entregar atividade, as notas começam a oscilar, o professor percebe que ele participa menos. O problema é que essas informações ficam espalhadas — na chamada, no diário de classe, nas notas, em anotações soltas da coordenação — e raramente alguém consegue juntar tudo isso a tempo de agir.

## [0:30–1:00] — Por que não é só "um sistema de risco"

A maioria das soluções que existem tenta resolver isso de um jeito específico: calcular um score de risco e gerar um ranking dos alunos mais críticos. Só que isso rotula o aluno, e não ajuda muito o professor ou o coordenador na prática. A pergunta que eu quis responder foi outra: não "quem é o aluno de risco", mas **o que mudou na trajetória desse aluno recentemente, e por que isso merece ser olhado com atenção**.

## [1:00–2:00] — Como o sistema funciona

O sistema parte de dados que já fazem parte da rotina escolar: presença, notas, atividades entregues ou não, e observações que o próprio professor registra em texto livre — coisas como "o aluno participou menos essa semana e não entregou a última atividade". A partir disso, o sistema acompanha a trajetória do aluno ao longo do tempo e identifica mudanças de padrão: uma queda progressiva de frequência, um aumento de atividades não entregues, uma combinação desses sinais. E o mais importante: cada mudança apontada vem junto com a evidência que a sustenta — o registro, a data, a origem — nunca uma afirmação solta tipo "a IA identificou risco alto". A partir daí, a coordenação pedagógica pode abrir um acompanhamento, registrar ações e definir próximos passos. A decisão continua sempre sendo humana.

## [2:00–2:25] — E o Machine Learning?

O projeto também explora, de forma experimental, se um modelo de Machine Learning treinado em dados sintéticos consegue reconhecer padrões associados a esses sinais de deterioração. Mas isso é tratado como o que é: um experimento acadêmico sobre um dataset controlado, nunca uma previsão real sobre o futuro de um aluno.

## [2:25–2:45] — Tecnologia

No back-end, uso Python com FastAPI e PostgreSQL; no front-end, React; e a camada de Machine Learning é construída com Scikit-Learn, sobre uma base de dados sintética, já que é um projeto de conclusão de curso e não trabalho com dados reais de estudantes.

## [2:45–3:00] — Fechamento

No fim, o objetivo desse projeto não é prever com certeza quem vai abandonar a escola. É mostrar como informações que já existem no dia a dia da escola podem ser organizadas pra dar visibilidade antecipada — e evidência — pra quem já cuida desses alunos de perto.
