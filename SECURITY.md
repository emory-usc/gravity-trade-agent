# Security Policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in this project, please
report it privately rather than opening a public issue. Email the maintainer
with a description, reproduction steps, and any proposed fix. We will respond
within 72 hours and work with you on a fix and coordinated disclosure.

Do **not** include live secrets, credentials, or real market data in any report.

## Security posture

- **No secrets in the repository.** All credentials are resolved at runtime from
  Azure Key Vault via a managed identity (or from environment variables in local
  development). See `src/gravity_trade/secret_store.py`.
- **Least-privilege identity.** The container app uses a user-assigned managed
  identity granted only `Key Vault Secrets User` and `Cosmos DB Data
  Contributor` (scoped via RBAC) — see `infra/main.bicep`.
- **Network isolation.** Key Vault and Cosmos DB are reachable only through
  private endpoints; public network access is disabled.
- **Container hardening.** The runtime image runs as a non-root user and ships
  only the application (multi-stage build).
- **Supply chain.** CI scans the built image for vulnerabilities (Trivy), and
  Dependabot keeps Python, Docker, and GitHub Actions dependencies current.

## Supported versions

Only the latest `main` branch is supported for security fixes.
