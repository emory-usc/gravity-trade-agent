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
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # Gravity Trade tuning knobs.
    high_conviction_threshold: int = 4  # 4+/6 signals = high conviction
    max_pain_near_pct: float = 0.005  # within 0.5% of max pain = neutral

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key)


def get_settings() -> Settings:
    return Settings()
