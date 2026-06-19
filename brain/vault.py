"""Vault I/O: parse and write Obsidian-style Markdown notes with YAML frontmatter.

All writes are non-destructive by default: filing a note picks a non-colliding
filename rather than overwriting an existing file.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .config import FOLDERS
from .models import Frontmatter, Note

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Turn a title into a filesystem- and wikilink-safe slug."""
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "note"


def parse_note(path: Path, vault_root: Path) -> Note:
    """Parse a single .md file into a Note. Tolerates missing frontmatter."""
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if match:
        meta = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
    else:
        meta = {}
        body = raw.strip()

    rel = path.relative_to(vault_root).as_posix()
    folder = rel.split("/", 1)[0]
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    frontmatter = Frontmatter(
        title=str(meta.get("title") or path.stem.replace("-", " ").title()),
        tags=[str(t) for t in tags],
        created=str(meta.get("created") or Frontmatter.today()),
    )
    return Note(path=rel, folder=folder, frontmatter=frontmatter, body=body)


def load_notes(vault_root: Path, folders: tuple[str, ...] = FOLDERS) -> list[Note]:
    """Load every note in the vault, sorted by path for deterministic output."""
    notes: list[Note] = []
    for folder in folders:
        folder_path = vault_root / folder
        if not folder_path.is_dir():
            continue
        for md in sorted(folder_path.glob("*.md")):
            notes.append(parse_note(md, vault_root))
    return sorted(notes, key=lambda n: n.path)


def render_note(frontmatter: Frontmatter, body: str) -> str:
    """Serialize a note back to Markdown with a YAML frontmatter block."""
    meta = {
        "title": frontmatter.title,
        "tags": frontmatter.tags,
        "created": frontmatter.created,
    }
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


def unique_path(vault_root: Path, folder: str, slug: str) -> Path:
    """Pick a non-colliding path: notes/foo.md, then foo-2.md, foo-3.md ..."""
    base = vault_root / folder
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / f"{slug}.md"
    counter = 2
    while candidate.exists():
        candidate = base / f"{slug}-{counter}.md"
        counter += 1
    return candidate


def write_note(
    vault_root: Path, folder: str, frontmatter: Frontmatter, body: str
) -> Path:
    """Write a note into a folder without overwriting anything. Returns the path."""
    path = unique_path(vault_root, folder, slugify(frontmatter.title))
    path.write_text(render_note(frontmatter, body), encoding="utf-8")
    return path
