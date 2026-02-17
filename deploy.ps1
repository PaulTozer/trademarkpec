# ---------------------------------------------------------------------------
# Deploy Trademark PEC to Azure Container Apps (PowerShell)
# ---------------------------------------------------------------------------
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#
# Usage:
#   .\deploy.ps1
#
# Set these environment variables before running:
#   $env:AZURE_AI_ENDPOINT = "https://..."
#   $env:AZURE_AI_API_KEY  = "..."
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# ---------- Configurable ----------
$RESOURCE_GROUP    = if ($env:RESOURCE_GROUP)    { $env:RESOURCE_GROUP }    else { "trademarkpec-rg" }
$LOCATION          = if ($env:LOCATION)          { $env:LOCATION }          else { "swedencentral" }
$ACR_NAME          = if ($env:ACR_NAME)          { $env:ACR_NAME }          else { "trademarkpecacr" }
$CONTAINER_APP_ENV = if ($env:CONTAINER_APP_ENV) { $env:CONTAINER_APP_ENV } else { "trademarkpec-env" }
$CONTAINER_APP     = if ($env:CONTAINER_APP_NAME){ $env:CONTAINER_APP_NAME} else { "trademarkpec" }
$IMAGE_NAME        = "trademarkpec"
$IMAGE_TAG         = "latest"

# ---------- Validate secrets ----------
if (-not $env:AZURE_AI_ENDPOINT -or -not $env:AZURE_AI_API_KEY) {
    Write-Error "Set `$env:AZURE_AI_ENDPOINT and `$env:AZURE_AI_API_KEY before running."
    exit 1
}
$AZURE_AI_MODEL = if ($env:AZURE_AI_MODEL) { $env:AZURE_AI_MODEL } else { "gpt-5.2-chat" }

Write-Host "=== 1/6  Creating Resource Group ===" -ForegroundColor Cyan
az group create --name $RESOURCE_GROUP --location $LOCATION --output none

Write-Host "=== 2/6  Creating Azure Container Registry ===" -ForegroundColor Cyan
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true --output none

Write-Host "=== 3/6  Building image in ACR ===" -ForegroundColor Cyan
az acr build --registry $ACR_NAME --image "${IMAGE_NAME}:${IMAGE_TAG}" . --output none

Write-Host "=== 4/6  Creating Container Apps Environment ===" -ForegroundColor Cyan
az containerapp env create --name $CONTAINER_APP_ENV --resource-group $RESOURCE_GROUP --location $LOCATION --output none 2>$null

$ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv
$ACR_PASSWORD     = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv

Write-Host "=== 5/6  Deploying Container App ===" -ForegroundColor Cyan
az containerapp create `
    --name $CONTAINER_APP `
    --resource-group $RESOURCE_GROUP `
    --environment $CONTAINER_APP_ENV `
    --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" `
    --registry-server $ACR_LOGIN_SERVER `
    --registry-username $ACR_NAME `
    --registry-password $ACR_PASSWORD `
    --target-port 8080 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 3 `
    --cpu 0.5 `
    --memory 1.0Gi `
    --env-vars "AZURE_AI_ENDPOINT=$($env:AZURE_AI_ENDPOINT)" "AZURE_AI_API_KEY=secretref:azure-ai-api-key" "AZURE_AI_MODEL=$AZURE_AI_MODEL" `
    --secrets "azure-ai-api-key=$($env:AZURE_AI_API_KEY)" `
    --output none

Write-Host "=== 6/6  Getting Application URL ===" -ForegroundColor Cyan
$FQDN = az containerapp show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  Deployment complete!" -ForegroundColor Green
Write-Host "  App URL:     https://$FQDN"
Write-Host "  OpenAPI:     https://$FQDN/openapi.json"
Write-Host "  Health:      https://$FQDN/health"
Write-Host "  Agent API:   POST https://$FQDN/classify"
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To use as an Azure AI Foundry agent tool, register"
Write-Host "the OpenAPI spec URL in your Foundry project."
