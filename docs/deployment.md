# Azure deployment

How the Gravity Trade agent reaches production in Azure. Everything is
parameterized — swap `namePrefix`, `location`, and the container image; no
real credentials or resource names are committed.

## Architecture

```
                                ┌────────────────────────────────────────┐
                                │          Azure (westus3)               │
   Ingress (HTTPS + API key) ──▶│  VNet                                   │
                                │  ├─ Container Apps (scale-to-zero 0→3) │
                                │  │   ├─ gravity-trade-agent :8080      │
                                │  │   │   (/health, /ready, /analyze)   │
                                │  │   └─ user-assigned identity ──────┐ │
                                │  │                                    │ │
                                │  ├─ endpoints subnet ── private ──────┤ │
                                │  │   endpoints (Key Vault, Cosmos)    │ │
                                │  └─ private DNS zones                  │ │
                                │                                        │
                                │  Key Vault (RBAC, purge-protected) ◀───┤
                                │  Cosmos DB (serverless, /ticker) ◀─────┘
                                │  App Insights ◀── metrics/logs ────────┘
                                │  Alert rules ──▶ action group
                                └────────────────────────────────────────┘
```

| Resource | Purpose |
|----------|---------|
| **Container Apps** | Runs the FastAPI service with liveness **and** readiness probes, API-key auth on `/analyze`, and scale-to-zero (0→3 replicas). |
| **Key Vault** | RBAC-enabled, purge-protected, **private endpoint only**. Holds the OpenAI key and the service API key, read via managed identity. |
| **Cosmos DB** | Serverless, **private endpoint only**. Every `SignalBundle` / `TradeThesis` is upserted here, partitioned by ticker. |
| **VNet + private endpoints** | App egress and PaaS access stay on a private network; public access to Key Vault and Cosmos is disabled. |
| **Application Insights + Log Analytics** | Conviction/direction metrics and structured logs, exported via OpenTelemetry. |
| **Alert rules** | CPU health alert + a scan-error log alert, wired to an action group. |

## Prerequisites

- An Azure subscription and a resource group.
- `az` CLI logged in (`az login`).
- A container registry (GitHub Container Registry is used below).
- An OpenAI API key and a service API key to store in Key Vault.

## 1. Build and push the image

```bash
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
the VNet with its subnets, private endpoints + private DNS, Log Analytics,
App Insights, the managed identity, the RBAC grants, and the alert rules.

## 3. Store secrets in Key Vault

```bash
az keyvault secret set \
  --vault-name "<namePrefix>-kv" --name "openai-api-key" --value "$OPENAI_API_KEY"
az keyvault secret set \
  --vault-name "<namePrefix>-kv" --name "gravity-api-key" --value "$GRAVITY_API_KEY"
```

The app resolves `OPENAI_API_KEY` and `GRAVITY_API_KEY` by reading the
`openai-api-key` / `gravity-api-key` secrets from Key Vault using its managed
identity (`secret_store.get_secret` maps env names to Key Vault-safe names).

## 4. Verify

```bash
APP_URL=$(az containerapp show -g "$RESOURCE_GROUP" -n "<namePrefix>-app" \
  --query properties.configuration.ingress.fqdn -o tsv)

curl "https://$APP_URL/health"                 # liveness
curl "https://$APP_URL/ready"                  # readiness (dependency state)
curl -X POST "https://$APP_URL/analyze/NVDA" \
  -H "X-API-Key: $GRAVITY_API_KEY"             # requires the API key
```

## Networking

The app runs VNet-integrated with private egress. Key Vault and Cosmos DB have
`publicNetworkAccess: Disabled` and are reachable only through private
endpoints; private DNS zones (`privatelink.vaultcore.azure.net` and
`privatelink.documents.azure.com`) resolve their FQDNs to private IPs.

> For a multi-region Cosmos account, add per-region A records to the
> `privatelink.documents.azure.com` zone; the single-region case is covered.

## Observability & alerting

With `APPLICATIONINSIGHTS_CONNECTION_STRING` set, the service exports
`gravity.conviction`, `gravity.direction`, and `gravity.errors` metrics via
OpenTelemetry. Two alert rules ship with the Bicep:

- **CPU high** — metric alert (CPU > 90% for 5 minutes).
- **Scan errors** — log alert on `severityLevel >= 3` traces (pipeline failures).

Failures are loud by design: persistence and secret-read errors are logged at
ERROR level and counted, so the log alert fires instead of the failure being
silently swallowed.

## Alternative: bare-metal VM (systemd + cron)

The same code runs un-containerized, matching a classic VM deployment:

```bash
uv sync --extra web
sudo cp deploy/gravity-trade-agent.service /etc/systemd/system/
sudo systemctl enable --now gravity-trade-agent

# Cron for the weekly cadence (Mon entry scan, Fri 2pm exit)
crontab -e
#   0 9 * * 1  cd /opt/gravity-trade-agent && uv run gravity analyze NVDA >> /var/log/gravity.log 2>&1
```

The same secrets come from Key Vault via managed identity, and the same Cosmos
container holds the history.

## CI/CD

`.github/workflows/deploy.yml` automates steps 1–3: build + push the image to
GHCR, scan it with Trivy, deploy the Bicep, and inject the secrets into Key
Vault. Required repository secrets: `AZURE_CREDENTIALS` (service principal),
`AZURE_RESOURCE_GROUP`, `KEYVAULT_NAME`, `ALERT_EMAIL`, `OPENAI_API_KEY`, and
`GRAVITY_API_KEY`.
