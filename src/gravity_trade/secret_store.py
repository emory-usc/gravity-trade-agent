"""Secret resolution: Azure Key Vault via managed identity, environment fallback.

In production the app authenticates to Key Vault with its managed identity —
no keys baked into the image, no ``.env`` committed. In local development,
secrets come from environment variables (loaded from ``.env`` by ``config``).

Precedence: an explicit environment variable wins, then Key Vault.
"""

from __future__ import annotations

import os

_KEY_VAULT_URL_ENV = "AZURE_KEY_VAULT_URL"


def _key_vault_client():
    """Return a Key Vault ``SecretClient`` bound to managed identity, else None.

    Returns None when the Azure SDKs are absent (dev install) or when no vault
    URL is configured, so callers can silently fall back to environment vars.
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        return None

    vault_url = os.getenv(_KEY_VAULT_URL_ENV)
    if not vault_url:
        return None
    try:
        return SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    except Exception:
        return None


def get_secret(name: str, vault_name: str | None = None) -> str | None:
    """Resolve a secret by name. Returns None when it cannot be resolved.

    ``name`` is the environment-variable name (e.g. ``OPENAI_API_KEY``).
    ``vault_name`` defaults to the Key Vault-safe form (``openai-api-key``),
    since Key Vault secret names allow only alphanumerics and hyphens.
    """
    # 1. Explicit environment variable (local dev, tests, CI).
    env_val = os.getenv(name)
    if env_val:
        return env_val

    # 2. Key Vault via managed identity (production).
    client = _key_vault_client()
    if client is None:
        return None
    secret_name = vault_name or name.lower().replace("_", "-")
    try:
        return client.get_secret(secret_name).value
    except Exception:
        return None
