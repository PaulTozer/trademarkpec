#!/bin/bash
# ---------------------------------------------------------------------------
# Deploy Trademark PEC to Azure Container Apps
# ---------------------------------------------------------------------------
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Docker installed (for local build/push) OR use ACR build
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Set these environment variables before running (or they use defaults):
#   RESOURCE_GROUP, LOCATION, ACR_NAME, CONTAINER_APP_ENV, CONTAINER_APP_NAME,
#   AZURE_AI_ENDPOINT, AZURE_AI_API_KEY, AZURE_AI_MODEL
# ---------------------------------------------------------------------------

set -euo pipefail

# ---------- Configurable variables ----------
RESOURCE_GROUP="${RESOURCE_GROUP:-trademarkpec-rg}"
LOCATION="${LOCATION:-swedencentral}"
ACR_NAME="${ACR_NAME:-trademarkpecacr}"
CONTAINER_APP_ENV="${CONTAINER_APP_ENV:-trademarkpec-env}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-trademarkpec}"
IMAGE_NAME="trademarkpec"
IMAGE_TAG="latest"

# ---------- Azure AI Foundry secrets ----------
# These MUST be set in your shell or .env before running
if [ -z "${AZURE_AI_ENDPOINT:-}" ] || [ -z "${AZURE_AI_API_KEY:-}" ]; then
    echo "ERROR: AZURE_AI_ENDPOINT and AZURE_AI_API_KEY must be set."
    echo "  export AZURE_AI_ENDPOINT='https://...'"
    echo "  export AZURE_AI_API_KEY='...'"
    exit 1
fi
AZURE_AI_MODEL="${AZURE_AI_MODEL:-gpt-5.2-chat}"

echo "=== 1/6  Creating Resource Group ==="
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

echo "=== 2/6  Creating Azure Container Registry ==="
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output none

echo "=== 3/6  Building image in ACR ==="
az acr build \
    --registry "$ACR_NAME" \
    --image "${IMAGE_NAME}:${IMAGE_TAG}" \
    . \
    --output none

echo "=== 4/6  Creating Container Apps Environment ==="
az containerapp env create \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none 2>/dev/null || true   # ignore if exists

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

echo "=== 5/6  Deploying Container App ==="
az containerapp create \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APP_ENV" \
    --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PASSWORD" \
    --target-port 8080 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 3 \
    --cpu 0.5 \
    --memory 1.0Gi \
    --env-vars \
        "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT}" \
        "AZURE_AI_API_KEY=secretref:azure-ai-api-key" \
        "AZURE_AI_MODEL=${AZURE_AI_MODEL}" \
    --secrets "azure-ai-api-key=${AZURE_AI_API_KEY}" \
    --output none

echo "=== 6/6  Getting Application URL ==="
FQDN=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo "==========================================="
echo "  Deployment complete!"
echo "  App URL:     https://${FQDN}"
echo "  OpenAPI:     https://${FQDN}/openapi.json"
echo "  Health:      https://${FQDN}/health"
echo "  Agent API:   POST https://${FQDN}/classify"
echo "==========================================="
echo ""
echo "To use as an Azure AI Foundry agent tool, register"
echo "the OpenAPI spec URL in your Foundry project."
