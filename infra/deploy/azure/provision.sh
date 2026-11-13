#!/usr/bin/env bash
# Create the GigBid VM on Azure (Azure for Students works). Needs the Azure CLI and `az login` first.
#   bash infra/deploy/azure/provision.sh            # defaults below; override with env vars
# Result: an Ubuntu 24.04 VM with Docker, ports 80/443 open, and a public name
#   <DNS_LABEL>.<LOCATION>.cloudapp.azure.com  (Caddy gets an HTTPS certificate for it automatically)
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-gigbid-rg}"
LOCATION="${LOCATION:-eastus}"
VM_NAME="${VM_NAME:-gigbid-vm}"
VM_SIZE="${VM_SIZE:-Standard_B2ms}"          # 2 vCPU, 8 GB RAM: enough for the full stack on CPU
DNS_LABEL="${DNS_LABEL:-gigbid-$RANDOM}"
ADMIN_USER="${ADMIN_USER:-gigbid}"

az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
az vm create \
  --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --image Canonical:ubuntu-24_04-lts:server:latest \
  --size "$VM_SIZE" --admin-username "$ADMIN_USER" --generate-ssh-keys \
  --public-ip-sku Standard --public-ip-address-dns-name "$DNS_LABEL" \
  --os-disk-size-gb 64 --custom-data "$(dirname "$0")/cloud-init.yaml" --output none
az vm open-port --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --port 80 --priority 1010 --output none
az vm open-port --resource-group "$RESOURCE_GROUP" --name "$VM_NAME" --port 443 --priority 1020 --output none

FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv)"
echo "VM ready: ssh $ADMIN_USER@$FQDN"
echo "Next: SITE_HOST=$FQDN bash infra/deploy/azure/deploy.sh $ADMIN_USER@$FQDN"
