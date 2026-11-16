# Publicação na Azure

Runbook para publicar o Sinaliza numa VM Linux da Azure, com os três
containers do `docker-compose.yml` da raiz. Tudo aqui é executado por uma
pessoa; nada é disparado por CI, cron ou tarefa agendada.

Substitui o Plano A/B da Épica 6 (Oracle Cloud), que não se concretizou: a
camada sempre-gratuita da Oracle não tinha capacidade na região do Brasil.
Os scripts de verificação daquela época (`deploy/smoke-test.sh`,
`deploy/verify-always-on.sh`) continuam válidos e são usados na Etapa 5.

## Por que VM e não PaaS gratuito

Serviço gratuito de PaaS hiberna por inatividade, e a primeira requisição
depois disso paga uma penalidade que pode passar de 5 segundos — o
`plan-c-contingency-runbook.md` registra isso como renúncia explícita ao
RNF-01. Como a aplicação é aberta por um avaliador em horário que não
controlamos, "lento ao acordar" é indistinguível de "quebrado".

Uma VM com `restart: unless-stopped` não dorme.

## Pré-requisitos

- Azure CLI autenticado (`az login`). No Windows, o executável costuma ficar
  em `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd`, nem sempre no
  PATH do shell.
- Uma chave SSH dedicada — **não reaproveite a do GitHub**:

  ```sh
  ssh-keygen -t ed25519 -C sinaliza-azure -f ~/.ssh/sinaliza_azure -N ""
  ```

## Etapa 1 — Provisionar

```sh
deploy/azure/provision.sh
```

O script cria o resource group, a VM (Ubuntu 24.04, IP público **estático**,
rótulo DNS gratuito) e o NSG. Ele percorre uma lista de região×tamanho e fica
com a primeira combinação que tiver capacidade, começando por
`mexicocentral` — a única com capacidade comprovada nesta assinatura e a mais
próxima do Brasil.

Regras do NSG: **SSH apenas do IP de quem provisiona** (detectado via
`api.ipify.org`, nunca `0.0.0.0/0`); 80 e 443 abertos para a Internet.

Para forçar uma combinação: `LOCATION=canadacentral VM_SIZE=Standard_B2s deploy/azure/provision.sh`

Ao final o script imprime a **URL pública** no formato
`http://<rótulo>.<região>.cloudapp.azure.com`. É esse o endereço da entrega.

## Etapa 2 — Confirmar o primeiro boot

```sh
ssh -i ~/.ssh/sinaliza_azure azureuser@<IP> 'cloud-init status --wait; free -h; docker --version'
```

Espere `status: done`, 2 GB de swap ativos e o Docker respondendo. O
`cloud-init` leva ~3 minutos.

## Etapa 3 — Clonar e configurar

```sh
ssh -i ~/.ssh/sinaliza_azure azureuser@<IP>
git clone https://github.com/bruno-romeu/sinaliza.git /opt/sinaliza
cd /opt/sinaliza
```

Crie o `.env` **na VM**, com segredos gerados ali — nunca copie os de
desenvolvimento:

```sh
cat > /opt/sinaliza/.env <<EOF
POSTGRES_USER=sinaliza
POSTGRES_DB=sinaliza
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')
JWT_SECRET=$(openssl rand -base64 48 | tr -d '/+=')
JWT_EXPIRE_MINUTES=60
DEV_SEED_NAME=Coordenação Pedagógica
DEV_SEED_EMAIL=avaliacao@sinaliza.app
DEV_SEED_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=')
EOF
chmod 600 /opt/sinaliza/.env
```

`JWT_SECRET` precisa de **no mínimo 32 caracteres**: `Settings` valida e o
backend não sobe sem isso. O `.env` está no `.gitignore` e nunca é versionado.

Guarde `DEV_SEED_EMAIL` e `DEV_SEED_PASSWORD` — são as credenciais que vão no
item 3.2 do documento de entrega:

```sh
grep DEV_SEED /opt/sinaliza/.env
```

## Etapa 4 — Subir

```sh
cd /opt/sinaliza && docker compose up -d --build
```

O `docker-entrypoint.sh` do backend roda `alembic upgrade head` antes do
uvicorn, então o schema e o usuário semeado nascem com a stack. O primeiro
build leva alguns minutos.

## Etapa 5 — Verificar

```sh
curl -sf http://localhost/api/openapi.json > /dev/null && echo "backend ok"
docker compose ps
bash deploy/smoke-test.sh          # da Épica 6, continua válido
```

E de fora da VM, no seu navegador: abra a URL pública **numa janela anônima**
— é assim que o avaliador vai abrir, e é o que o checklist da entrega pede.

## Custo

Uma VM cobra por tempo **alocado**, não por acesso: ligada e ociosa custa
igual a ligada e em uso.

`shutdown` por dentro do sistema **não** para a cobrança — a VM fica
`Stopped` e o compute continua faturando. Só `deallocate` para:

```sh
deploy/azure/power.sh stop     # desaloca
deploy/azure/power.sh start    # religa
```

Mesmo desalocada, o disco gerenciado e o IP estático seguem custando alguns
centavos por mês.

**Não desaloque durante o período de avaliação.** Este runbook, ao contrário
do equivalente no projeto ecommerce, não instala desligamento automático — a
aplicação precisa responder a qualquer hora.

Crie um alerta de orçamento em *Cost Management → Budgets* antes de esquecer.

## HTTPS (opcional)

A entrega não exige TLS, e o Nginx hoje serve HTTP na 80. Se quiser
certificado, a porta 443 já está aberta no NSG e o rótulo
`*.cloudapp.azure.com` é validável pelo Let's Encrypt via HTTP-01 sem comprar
domínio.

Ao fazer isso, revise a CSP em `frontend/nginx.conf`: ela hoje é parcial e
não inclui `script-src`, pelo motivo registrado no histórico do projeto (o
bootstrap de tema é um `<script>` inline).
