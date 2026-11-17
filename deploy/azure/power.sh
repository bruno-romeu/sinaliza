#!/bin/sh
# Liga/desliga a VM de staging. Quem paga o credito e a VM ligada.
#
#   power.sh stop    DESALOCA (para de cobrar computacao)
#   power.sh start   liga e espera a API responder
#   power.sh status  estado da VM e do IP
#
# `stop` usa `az vm deallocate`, nao `az vm stop` nem `shutdown` dentro da VM:
# nestes dois a VM fica "Stopped" mas a Azure continua cobrando a computacao.
# Ao desalocar, so disco (~US$2-4/mes) e IP estatico (~US$3,65/mes) continuam.
set -eu

RG=${RG:-sinaliza-rg}
VM_NAME=${VM_NAME:-sinaliza}
ACTION=${1:-}

command -v az >/dev/null || { echo "Azure CLI (az) nao encontrado." >&2; exit 1; }

fqdn() {
    az network public-ip show --resource-group "$RG" \
        --name "${VM_NAME}PublicIP" --query dnsSettings.fqdn -o tsv
}

case "$ACTION" in
    stop)
        az vm deallocate --resource-group "$RG" --name "$VM_NAME"
        echo "VM desalocada. Computacao nao esta mais sendo cobrada."
        ;;
    start)
        az vm start --resource-group "$RG" --name "$VM_NAME"
        host=$(fqdn)
        echo "Aguardando http://$host/api/health/ (o stack sobe pelo systemd)..."
        i=0
        while [ "$i" -lt 30 ]; do
            if curl -fsS --max-time 5 -o /dev/null "http://$host/api/openapi.json" 2>/dev/null; then
                echo "No ar."
                exit 0
            fi
            i=$((i + 1))
            sleep 10
        done
        echo "API nao respondeu em 5 min; veja: ssh azureuser@$host 'cd /opt/sinaliza && docker compose ps'" >&2
        exit 1
        ;;
    status)
        az vm get-instance-view --resource-group "$RG" --name "$VM_NAME" \
            --query "instanceView.statuses[?starts_with(code,'PowerState')].displayStatus" -o tsv
        echo "http://$(fqdn)"
        ;;
    *)
        echo "Uso: $0 {start|stop|status}" >&2
        exit 2
        ;;
esac
