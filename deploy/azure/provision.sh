#!/bin/sh
# Cria (ou reaproveita) toda a infra Azure do staging, com o menor custo que
# ainda roda a stack. Idempotente: rodar de novo nao duplica nada.
#
# Uso:   az login && ./infra/azure/provision.sh
# Vars:  LOCATION, RG, VM_NAME, VM_SIZE, DNS_LABEL, SSH_KEY, SSH_SOURCE,
#        Nada aqui toca em segredos.
set -eu

CDPATH=''
export CDPATH
HERE=$(cd -- "$(dirname -- "$0")" && pwd)

# Azure for Students tem a policy "Allowed resource deployment regions": nesta
# assinatura so passam belgiumcentral, canadacentral, southafricanorth,
# mexicocentral e spaincentral (eastus2/brazilsouth dao RequestDisallowedByAzure).
# Confira a sua com `az policy assignment list --query "[].parameters" -o json`.
#
# Mesmo em regiao permitida, a Azure pode negar a VM por capacidade
# (SkuNotAvailable) — aconteceu com B2s em canadacentral. Essa falha e da
# validacao previa e nao custa nada, entao tentamos as combinacoes abaixo em
# ordem (todas 2 vCPU / 4 GiB, ~US$30-35/mes ligadas) e ficamos com a primeira
# aceita. LOCATION e/ou VM_SIZE forcam uma unica combinacao.
if [ -n "${LOCATION:-}${VM_SIZE:-}" ]; then
    CANDIDATES="${LOCATION:-mexicocentral}:${VM_SIZE:-Standard_B2s}"
else
    # mexicocentral primeiro: e a unica regiao desta assinatura com
    # capacidade comprovada para a familia B (a VM do ecommerce subiu la),
    # e e a mais proxima do Brasil -- menos latencia para quem avalia.
    CANDIDATES="mexicocentral:Standard_B2s mexicocentral:Standard_B2als_v2 \
canadacentral:Standard_B2s canadacentral:Standard_B2als_v2 canadacentral:Standard_B2ls_v2 \
spaincentral:Standard_B2s spaincentral:Standard_B2als_v2 \
belgiumcentral:Standard_B2s belgiumcentral:Standard_B2als_v2"
fi
RG=${RG:-sinaliza-rg}
VM_NAME=${VM_NAME:-sinaliza}
# Vira <label>.<regiao>.cloudapp.azure.com: DNS publico gratis, o Let's Encrypt
# valida nele normalmente e dispensa comprar dominio. Precisa ser unico na regiao.
DNS_LABEL=${DNS_LABEL:-$VM_NAME}
SSH_KEY=${SSH_KEY:-$HOME/.ssh/sinaliza_azure}

command -v az >/dev/null || { echo "Azure CLI (az) nao encontrado." >&2; exit 1; }
[ -f "$SSH_KEY.pub" ] || {
    echo "Falta $SSH_KEY.pub. Gere com: ssh-keygen -t ed25519 -C sinaliza-azure -f $SSH_KEY -N """ >&2
    exit 1
}
az account show >/dev/null 2>&1 || { echo "Rode 'az login' antes." >&2; exit 1; }

# SSH so do IP de quem provisiona. Nunca 0.0.0.0/0.
SSH_SOURCE=${SSH_SOURCE:-$(curl -fsS --max-time 10 https://api.ipify.org)/32}
case "$SSH_SOURCE" in
    */32) ;;
    *) echo "SSH_SOURCE invalido: '$SSH_SOURCE'" >&2; exit 1 ;;
esac

echo "Assinatura: $(az account show --query name -o tsv)"
echo "SSH liberado para: $SSH_SOURCE"

# O grupo pode ja existir (de uma tentativa anterior) em outra regiao: reaproveita.
FIRST_LOCATION=${CANDIDATES%%:*}
az group show --name "$RG" --output none 2>/dev/null ||
    az group create --name "$RG" --location "$FIRST_LOCATION" --output none

create_vm() {
    # Standard SSD de 30 GB (nao precisa de Premium) e IP estatico: o dinamico
    # muda a cada deallocate e quebraria o DNS.
    az vm create \
        --resource-group "$RG" \
        --name "$VM_NAME" \
        --location "$1" \
        --image Ubuntu2404 \
        --size "$2" \
        --admin-username azureuser \
        --authentication-type ssh \
        --ssh-key-values "$SSH_KEY.pub" \
        --storage-sku StandardSSD_LRS \
        --os-disk-size-gb 30 \
        --public-ip-sku Standard \
        --public-ip-address-allocation static \
        --public-ip-address-dns-name "$DNS_LABEL" \
        --nsg-rule NONE \
        --custom-data "$HERE/cloud-init.yaml" \
        --output none
}

if az vm show --resource-group "$RG" --name "$VM_NAME" --output none 2>/dev/null; then
    echo "VM $VM_NAME ja existe; pulando criacao."
else
    created=0
    for candidate in $CANDIDATES; do
        loc=${candidate%%:*}
        size=${candidate#*:}
        echo "Tentando $size em $loc ..."
        # A CLI da Azure as vezes explode num traceback proprio ao reportar o erro;
        # a causa real (SkuNotAvailable) continua no texto, entao casamos nele.
        if err=$(create_vm "$loc" "$size" 2>&1); then
            echo "Criada: $size em $loc."
            created=1
            break
        fi
        if printf '%s' "$err" | grep -Eq 'SkuNotAvailable|Capacity'; then
            echo "  sem capacidade para essa combinacao; proxima."
            continue
        fi
        printf '%s\n' "$err" >&2
        exit 1
    done
    if [ "$created" -ne 1 ]; then
        echo "Nenhuma combinacao regiao/tamanho tinha capacidade. Tente mais tarde ou peca ao suporte da Azure." >&2
        exit 1
    fi
fi

NSG="${VM_NAME}NSG"
rule() {
    az network nsg rule create --resource-group "$RG" --nsg-name "$NSG" \
        --name "$1" --priority "$2" --direction Inbound --access Allow \
        --protocol Tcp --destination-port-ranges "$3" \
        --source-address-prefixes "$4" --output none
}
rule ssh-owner 100 22 "$SSH_SOURCE"
rule http 110 80 Internet     # Let's Encrypt (HTTP-01) e redirect para HTTPS
rule https 120 443 Internet

# NAO ha desligamento automatico aqui, ao contrario do projeto ecommerce.
# A aplicacao e avaliada por terceiro, que pode abrir o link a qualquer hora:
# uma VM desalocada nao responde devagar -- ela nao responde. O modelo da
# entrega diz que aplicacao inacessivel torna o trabalho nao avaliado.
#
# O custo de manter ligada e pequeno perto desse risco. Crie um alerta de
# orcamento em Cost Management -> Budgets. Depois da avaliacao, desalocar e
# um comando: deploy/azure/power.sh stop

FQDN=$(az network public-ip show --resource-group "$RG" \
    --name "${VM_NAME}PublicIP" --query dnsSettings.fqdn -o tsv)
IP=$(az network public-ip show --resource-group "$RG" \
    --name "${VM_NAME}PublicIP" --query ipAddress -o tsv)

cat <<MSG

Pronto.
  URL publica: http://$FQDN
  IP:          $IP

Proximos passos (deploy/azure/README.md):
  1. Aguarde ~3 min e confirme o cloud-init:
       ssh -i $SSH_KEY azureuser@$IP 'cloud-init status --wait; free -h'
  2. Clone o repo e crie o .env de producao na VM (Etapa 3).
  3. docker compose up -d --build
  4. Rode o smoke test (Etapa 5).
  5. Crie o alerta de orcamento no portal.
MSG
