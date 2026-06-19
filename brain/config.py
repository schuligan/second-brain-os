"""Runtime configuration and environment detection.

The single source of truth for "are we in mock mode or real-LLM mode". Mock mode
is the default and runs fully offline with no API key; the real path activates
only when ANTHROPIC_API_KEY is present.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL_ID = "claude-opus-4-8"

# Folder taxonomy. Order matters for display.
FOLDERS = ("inbox", "notes", "daily", "projects", "references")

MOCK_BANNER = "[MOCK MODE — set ANTHROPIC_API_KEY for real LLM]"


@dataclass(frozen=True)
class Config:
    """Immutable runtime config resolved from the environment."""

    vault: Path
    model_id: str
    api_key: str | None

    @property
    def is_mock(self) -> bool:
        """True when no API key is configured (offline, deterministic)."""
        return not self.api_key

    @property
    def index_path(self) -> Path:
        """Where the embedding index is persisted (gitignored, rebuildable)."""
        return self.vault / ".brain" / "index.json"


def load_config(vault: Path | str | None = None) -> Config:
    """Resolve config from env vars, falling back to a sensible local vault."""
    resolved_vault = Path(vault) if vault else Path(os.environ.get("BRAIN_VAULT", "vault"))
    api_key = os.environ.get("ANTHROPIC_API_KEY") or None
    model_id = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    return Config(vault=resolved_vault.resolve(), model_id=model_id, api_key=api_key)
