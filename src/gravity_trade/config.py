"""Runtime configuration.

Everything here resolves from environment variables with sane defaults so the
offline pipeline runs with zero setup. Only the LLM-backed agent mode requires
an API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Project root (repo checkout) — used to locate bundled sample data.
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "sample"
EVALS_DIR = ROOT / "evals"


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one run."""

    # LLM provider (OpenAI-compatible). Only used by `gravity agent`.
    # Resolved via Key Vault (managed identity) in production, env var in dev.
    openai_api_key: str = field(default_factory=lambda: _resolve_api_key("OPENAI_API_KEY"))
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # API key protecting the HTTP service. Resolved via Key Vault in production.
    api_key: str = field(default_factory=lambda: _resolve_api_key("GRAVITY_API_KEY"))

    # Gravity Trade tuning knobs.
    high_conviction_threshold: int = 4  # 4+/6 signals = high conviction
    max_pain_near_pct: float = 0.005  # within 0.5% of max pain = neutral

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key)


def get_settings() -> Settings:
    return Settings()


def _resolve_api_key(name: str) -> str:
    """Resolve a secret via Key Vault (managed identity) or environment."""
    try:
        from gravity_trade.secret_store import get_secret

        return get_secret(name) or ""
    except Exception:
        return os.getenv(name, "")
