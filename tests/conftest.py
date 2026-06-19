"""Shared pytest fixtures: a temporary vault seeded with synthetic notes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the package is importable when running `pytest` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brain.config import Config  # noqa: E402
from brain.models import Frontmatter  # noqa: E402
from brain.vault import render_note  # noqa: E402

_SEED = {
    "notes/overnight-oats.md": (
        "Overnight Oats Formula",
        ["cooking"],
        "Rolled oats, milk, yogurt, and chia seeds steeped overnight. "
        "An easy no-effort weekday breakfast.",
    ),
    "notes/deep-work-routine.md": (
        "Deep Work Routine",
        ["productivity", "reading"],
        "Two 90 minute focus blocks before lunch with the phone in another room. "
        "Protect the calendar so the blocks survive.",
    ),
    "references/atomic-habits-notes.md": (
        "Atomic Habits Notes",
        ["reading", "productivity"],
        "Book notes on the habit loop: cue, craving, response, reward. "
        "You fall to the level of your systems.",
    ),
    "projects/trailmix-app-idea.md": (
        "Trailmix Hiking App",
        ["side-project", "ideas"],
        "A hiking companion app idea. Offline GPX import, waypoint alerts, "
        "and an adaptive packing checklist. Build it as a thin slice first.",
    ),
}


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """A temp vault with the five taxonomy folders and a few seeded notes."""
    for folder in ("inbox", "notes", "daily", "projects", "references"):
        (tmp_path / folder).mkdir(parents=True)

    for rel, (title, tags, body) in _SEED.items():
        fm = Frontmatter(title=title, tags=tags, created="2026-06-18")
        (tmp_path / rel).write_text(render_note(fm, body), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def config(vault: Path) -> Config:
    """A mock-mode config pointing at the temp vault (no API key)."""
    return Config(vault=vault, model_id="claude-opus-4-8", api_key=None)
