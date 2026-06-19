"""Embedding index: build, persist, search, and suggest links.

The index is a plain JSON file mapping note path -> embedding vector. It is
rebuildable at any time with `brain index`, so it lives under .brain/ and is
gitignored.
"""

from __future__ import annotations

import json
from pathlib import Path

from .embedder import cosine, embed
from .models import LinkSuggestion, Note, SearchHit
from .vault import load_notes

SNIPPET_LEN = 160
DEFAULT_TOP_K = 5
LINK_THRESHOLD = 0.12  # min cosine similarity to suggest a wikilink


def _snippet(note: Note, query_tokens: set[str]) -> str:
    """Pick a short, query-aware snippet from the note body."""
    body = note.body.replace("\n", " ").strip()
    if not body:
        return note.frontmatter.title
    lowered = body.lower()
    for token in query_tokens:
        idx = lowered.find(token)
        if idx != -1:
            start = max(0, idx - 40)
            end = min(len(body), idx + SNIPPET_LEN - 40)
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(body) else ""
            return f"{prefix}{body[start:end].strip()}{suffix}"
    return body[:SNIPPET_LEN] + ("..." if len(body) > SNIPPET_LEN else "")


class BrainIndex:
    """In-memory embedding index over the vault, with JSON persistence."""

    def __init__(self, notes: list[Note], vectors: dict[str, list[float]]):
        self.notes = notes
        self.vectors = vectors
        self._by_path = {n.path: n for n in notes}

    @classmethod
    def build(cls, vault_root: Path) -> BrainIndex:
        """Embed every note in the vault from scratch."""
        notes = load_notes(vault_root)
        vectors = {n.path: embed(n.searchable_text) for n in notes}
        return cls(notes, vectors)

    def save(self, index_path: Path) -> None:
        """Persist vectors to a JSON file (rebuildable cache)."""
        index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"dim": len(next(iter(self.vectors.values()), [])), "vectors": self.vectors}
        index_path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, vault_root: Path, index_path: Path) -> BrainIndex:
        """Load notes fresh and reuse cached vectors when present, else rebuild."""
        notes = load_notes(vault_root)
        if not index_path.exists():
            return cls.build(vault_root)
        cached = json.loads(index_path.read_text(encoding="utf-8")).get("vectors", {})
        vectors = {
            n.path: cached.get(n.path) or embed(n.searchable_text) for n in notes
        }
        return cls(notes, vectors)

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[SearchHit]:
        """Return the top_k notes most similar to the query."""
        query_vec = embed(query)
        query_tokens = {t for t in query.lower().split() if len(t) >= 2}
        scored = [
            (cosine(query_vec, self.vectors[n.path]), n)
            for n in self.notes
            if n.path in self.vectors
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        hits: list[SearchHit] = []
        for score, note in scored[:top_k]:
            if score <= 0.0:
                continue
            hits.append(
                SearchHit(
                    path=note.path,
                    title=note.frontmatter.title,
                    score=round(score, 4),
                    snippet=_snippet(note, query_tokens),
                )
            )
        return hits

    def related(self, note: Note, top_k: int = 3, threshold: float = LINK_THRESHOLD):
        """Return notes most similar to a given note (excluding itself)."""
        if note.path not in self.vectors:
            return []
        target = self.vectors[note.path]
        scored = [
            (cosine(target, self.vectors[other.path]), other)
            for other in self.notes
            if other.path != note.path and other.path in self.vectors
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [(round(s, 4), n) for s, n in scored[:top_k] if s >= threshold]

    def suggest_links(self, threshold: float = LINK_THRESHOLD) -> list[LinkSuggestion]:
        """Suggest wikilinks for notes that do not already link to a related note."""
        suggestions: list[LinkSuggestion] = []
        for note in self.notes:
            for score, other in self.related(note, threshold=threshold):
                wikilink = f"[[{other.slug}]]"
                if wikilink in note.body:
                    continue
                suggestions.append(
                    LinkSuggestion(
                        source_path=note.path,
                        target_slug=other.slug,
                        score=score,
                    )
                )
        return suggestions

    def get(self, path: str) -> Note | None:
        return self._by_path.get(path)
