"""Pydantic data models for notes, classifications, and search results."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .config import FOLDERS


class Frontmatter(BaseModel):
    """YAML frontmatter block at the top of every note."""

    title: str
    tags: list[str] = Field(default_factory=list)
    created: str  # ISO date string, e.g. "2026-06-18"

    @staticmethod
    def today() -> str:
        return date.today().isoformat()


class Note(BaseModel):
    """A parsed Markdown note: frontmatter + body + provenance."""

    path: str  # relative path within the vault, e.g. "notes/oatmeal.md"
    folder: str
    frontmatter: Frontmatter
    body: str

    @property
    def slug(self) -> str:
        """Filename without extension, used as the wikilink target."""
        return self.path.rsplit("/", 1)[-1].removesuffix(".md")

    @property
    def searchable_text(self) -> str:
        """Concatenated text used for embedding and search.

        The title and tags are repeated so they carry more weight than ordinary
        body words: shared tags and titles are a strong relatedness signal, and
        without this boost short notes barely register similarity at all.
        """
        title = self.frontmatter.title
        tags = " ".join(self.frontmatter.tags)
        return f"{title} {title}\n{tags} {tags} {tags}\n{self.body}"


class Classification(BaseModel):
    """Output of the capture agent for one raw thought."""

    title: str
    folder: str
    tags: list[str]
    summary: str
    related_slugs: list[str] = Field(default_factory=list)
    reasoning: str = ""

    def normalized(self) -> Classification:
        """Return a copy with the folder coerced into the known taxonomy."""
        folder = self.folder if self.folder in FOLDERS else "notes"
        return self.model_copy(update={"folder": folder})


class SearchHit(BaseModel):
    """One ranked result from an embeddings search."""

    path: str
    title: str
    score: float
    snippet: str


class LinkSuggestion(BaseModel):
    """A proposed wikilink between two existing notes."""

    source_path: str
    target_slug: str
    score: float
