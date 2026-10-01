"""Secret resolution: Azure Key Vault via managed identity, environment fallback.

In production the app authenticates to Key Vault with its managed identity —
no keys baked into the image, no ``.env`` committed. In local development,
secrets come from environment variables (loaded from ``.env`` by ``config``).

Precedence: an explicit environment variable wins, then Key Vault.

The SecretClient is constructed once and cached (connection reuse); a failed
read is logged loudly rather than silently swallowed.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("gravity_trade")

_KEY_VAULT_URL_ENV = "AZURE_KEY_VAULT_URL"

_client = None
_client_resolved = False


def _key_vault_client():
    """Return a cached Key Vault SecretClient, or None if unavailable."""
    global _client, _client_resolved
    if _client_resolved:
        return _client
    _client_resolved = True

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        _client = None
        return None

    vault_url = os.getenv(_KEY_VAULT_URL_ENV)
    if not vault_url:
        _client = None
        return None
    try:
        _client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    except Exception:
        log.exception("Failed to construct Key Vault client")
        _client = None
    return _client


def get_secret(name: str, vault_name: str | None = None) -> str | None:
    """Resolve a secret by name. Returns None when it cannot be resolved.

    ``name`` is the environment-variable name (e.g. ``OPENAI_API_KEY``).
    ``vault_name`` defaults to the Key Vault-safe form (``openai-api-key``),
    since Key Vault secret names allow only alphanumerics and hyphens.
    """
    env_val = os.getenv(name)
    if env_val:
        return env_val

    client = _key_vault_client()
    if client is None:
        return None
    secret_name = vault_name or name.lower().replace("_", "-")
    try:
        return client.get_secret(secret_name).value
    except Exception:
        log.exception("Failed to read secret %r from Key Vault", secret_name)
        return None


def check_health() -> tuple[bool, str]:
    """Readiness signal for the Key Vault dependency."""
    if not os.getenv(_KEY_VAULT_URL_ENV):
        return (True, "not_configured")
    return (True, "ok") if _key_vault_client() is not None else (False, "unavailable")
