"""LLM client with two interchangeable backends.

- MockLLM: deterministic, offline. Classifies via keyword heuristics. Default.
- AnthropicLLM: real path, used only when ANTHROPIC_API_KEY is present and the
  `anthropic` package is installed.

Both expose the same `classify(text, candidates)` interface, so the rest of the
app never branches on which backend is live.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from .config import Config
from .models import Classification


def _matches(keyword: str, words: set[str], lowered: str) -> bool:
    """Whole-word keyword match. Multi-word keywords fall back to substring.

    Whole-word matching avoids false positives like "bread" matching "read".
    """
    if " " in keyword:
        return keyword in lowered
    return keyword in words

# Keyword -> folder/tag heuristics for the mock classifier. Generic personal-
# knowledge topics only (books, recipes, ideas, meetings for a side project).
_FOLDER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "references": ("book", "article", "paper", "read", "author", "quote", "recipe"),
    "projects": ("project", "launch", "milestone", "sprint", "ship", "roadmap", "build"),
    "daily": ("today", "yesterday", "standup", "log", "journal"),
}

_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cooking": ("recipe", "recipes", "oats", "cooking", "kitchen", "meal"),
    "reading": ("book", "books", "reading", "author", "chapter", "novel"),
    "ideas": ("idea", "ideas", "maybe", "what if", "concept"),
    "meeting": ("meeting", "standup", "sync", "agenda", "kickoff"),
    "side-project": ("project", "app", "prototype", "feature"),
    "productivity": ("habit", "habits", "routine", "routines", "focus", "workflow"),
}


class LLM(Protocol):
    """Common interface for mock and real backends."""

    def classify(self, text: str, candidate_slugs: list[str]) -> Classification: ...


class MockLLM:
    """Deterministic keyword-based classifier. No network."""

    def classify(self, text: str, candidate_slugs: list[str]) -> Classification:
        lowered = text.lower()
        words = set(re.findall(r"[a-z]+", lowered))

        folder = "notes"
        for candidate_folder, keywords in _FOLDER_KEYWORDS.items():
            if any(_matches(kw, words, lowered) for kw in keywords):
                folder = candidate_folder
                break

        tags = sorted(
            tag
            for tag, keywords in _TAG_KEYWORDS.items()
            if any(_matches(kw, words, lowered) for kw in keywords)
        )
        if not tags:
            tags = ["inbox"]

        # Title: first sentence/line, trimmed.
        first_line = text.strip().splitlines()[0] if text.strip() else "Untitled note"
        title = first_line.strip(".!?").strip()
        title = (title[:60] + "...") if len(title) > 60 else title

        summary = text.strip().replace("\n", " ")
        summary = (summary[:200] + "...") if len(summary) > 200 else summary

        return Classification(
            title=title or "Untitled note",
            folder=folder,
            tags=tags,
            summary=summary,
            related_slugs=candidate_slugs[:3],
            reasoning="mock: keyword heuristics",
        )


_SYSTEM_PROMPT = (
    "You are a note-filing assistant for a Markdown second brain. "
    "Classify the user's raw thought into one folder of: inbox, notes, daily, "
    "projects, references. Suggest 1-4 short kebab-case tags and a concise title. "
    "Pick up to 3 related notes from the provided candidate slugs. "
    "Respond ONLY with a JSON object with keys: title, folder, tags, summary, "
    "related_slugs, reasoning."
)


class AnthropicLLM:
    """Real Anthropic-backed classifier. Activated only when a key is present."""

    def __init__(self, config: Config):
        import anthropic  # imported lazily so mock mode needs no dependency

        self._client = anthropic.Anthropic(api_key=config.api_key)
        self._model = config.model_id

    def classify(self, text: str, candidate_slugs: list[str]) -> Classification:
        user = (
            f"Raw thought:\n{text}\n\n"
            f"Candidate related note slugs: {candidate_slugs}\n\n"
            "Return the JSON object now."
        )
        message = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        raw = "".join(block.text for block in message.content if block.type == "text")
        data = json.loads(_extract_json(raw))
        return Classification(**data)


def _extract_json(raw: str) -> str:
    """Pull the first {...} block out of a model response."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model response: {raw!r}")
    return raw[start : end + 1]


def get_llm(config: Config) -> LLM:
    """Return the real backend if a key is present, else the mock backend."""
    if config.is_mock:
        return MockLLM()
    return AnthropicLLM(config)
