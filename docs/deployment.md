# Azure deployment

How the Gravity Trade agent reaches production in Azure. Everything is
parameterized — swap `namePrefix`, `location`, and the container image; no
real credentials or resource names are committed.

## Architecture

```
                              ┌──────────────────────────────┐
                              │        Azure (westus3)        │
                              │                                │
   Ingress (HTTPS) ──────────▶│  Container Apps                │
                              │  ├─ gravity-trade-agent        │
                              │  │   (FastAPI, :8080)          │
                              │  └─ user-assigned identity ──┐ │
                              │                              │ │
                              │  Key Vault  ◀── RBAC ────────┤ │
                              │  (openai-api-key)            │ │
                              │                              │ │
                              │  Cosmos DB   ◀── RBAC ───────┘ │
                              │  (serverless, /ticker)         │
                              │                                │
                              │  App Insights ◀── metrics ─────┘
                              │  Log Analytics ◀── logs ───────┘
                              │  Alert rules ──▶ action group   │
                              └────────────────────────────────┘
```

| Resource | Purpose |
|----------|---------|
| **Container Apps** | Runs the FastAPI service (`/health`, `/analyze/{ticker}`) with a liveness probe and a user-assigned managed identity. |
| **Key Vault** | RBAC-enabled and purge-protected; holds the OpenAI API key. The app reads it via managed identity — never in the image or `.env`. |
| **Cosmos DB** | Serverless; every `SignalBundle` / `TradeThesis` is upserted here, partitioned by ticker, for replay and eval. |
| **Application Insights + Log Analytics** | Conviction/direction metrics and structured logs, exported via OpenTelemetry. |
| **Alert rules** | A CPU health alert wired to an action group; extendable to domain alerts (pipeline failure, conviction spike, scan staleness). |

## Prerequisites

- An Azure subscription and a resource group.
- `az` CLI logged in (`az login`).
- A container registry (GitHub Container Registry is used below).
- An OpenAI API key to store in Key Vault.

## 1. Build and push the image

```bash
# Tag and push to GHCR (or your ACR).
export IMAGE=ghcr.io/emory-usc/gravity-trade-agent:latest
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

## 2. Deploy the infrastructure

```bash
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json \
               containerImage="$IMAGE" \
               alertEmail="you@example.com"
```

This provisions the Container Apps environment + app, Key Vault, Cosmos DB,
Log Analytics, App Insights, the managed identity, the RBAC grants, and the
alert rule — all in one deployment.

## 3. Store the OpenAI key in Key Vault

```bash
az keyvault secret set \
  --vault-name "<namePrefix>-kv" \
  --name "openai-api-key" \
  --value "$OPENAI_API_KEY"
```

The app resolves `OPENAI_API_KEY` by reading the `openai-api-key` secret from
Key Vault using its managed identity (`secret_store.get_secret` maps the env
name to the Key Vault-safe name).

## 4. Verify

```bash
APP_URL=$(az containerapp show -g "$RESOURCE_GROUP" -n "<namePrefix>-app" \
  --query properties.configuration.ingress.fqdn -o tsv)

curl "https://$APP_URL/health"
curl -X POST "https://$APP_URL/analyze/NVDA"
```

## Observability

With `APPLICATIONINSIGHTS_CONNECTION_STRING` set (injected by Bicep), the
service exports a `gravity.conviction` histogram and a `gravity.direction`
counter via OpenTelemetry. Those metrics, plus structured logs, surface in
Application Insights and can be charted in Azure Managed Grafana.

## Alternative: bare-metal VM (systemd + cron)

The same code runs un-containerized, matching a classic VM deployment:

```bash
# On the VM
uv sync --extra web
sudo cp deploy/gravity-trade-agent.service /etc/systemd/system/
sudo systemctl enable --now gravity-trade-agent

# Cron for the weekly cadence (Mon entry scan, Fri 2pm exit)
crontab -e
#   0 9 * * 1  cd /opt/gravity-trade-agent && uv run gravity analyze NVDA >> /var/log/gravity.log 2>&1
```

This is the path the framework's live trading stack already follows — the same
secrets come from Key Vault via managed identity, and the same Cosmos container
holds the history.

## CI/CD

`.github/workflows/deploy.yml` automates steps 1–3: build + push the image to
GHCR on a tag or manual dispatch, deploy the Bicep, and inject the OpenAI key
into Key Vault. Required repository secrets: `AZURE_CREDENTIALS` (service
principal), `AZURE_RESOURCE_GROUP`, `KEYVAULT_NAME`, `ALERT_EMAIL`, and
`OPENAI_API_KEY`.
