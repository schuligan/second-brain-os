"""Unit tests for vault parsing and non-destructive writes."""

from __future__ import annotations

from pathlib import Path

from brain.models import Frontmatter
from brain.vault import load_notes, parse_note, slugify, write_note


def test_slugify_produces_safe_slugs():
    assert slugify("Overnight Oats Formula!") == "overnight-oats-formula"
    assert slugify("   ") == "note"


def test_parse_note_reads_frontmatter(vault: Path):
    note = parse_note(vault / "notes" / "overnight-oats.md", vault)
    assert note.frontmatter.title == "Overnight Oats Formula"
    assert "cooking" in note.frontmatter.tags
    assert note.folder == "notes"
    assert note.slug == "overnight-oats"


def test_load_notes_is_sorted_and_complete(vault: Path):
    notes = load_notes(vault)
    paths = [n.path for n in notes]
    assert paths == sorted(paths)
    assert "references/atomic-habits-notes.md" in paths


def test_write_note_never_overwrites(vault: Path):
    fm = Frontmatter(title="Cold Brew", tags=["cooking"], created="2026-06-18")

    first = write_note(vault, "notes", fm, "Body one")
    second = write_note(vault, "notes", fm, "Body two")

    assert first != second
    assert first.name == "cold-brew.md"
    assert second.name == "cold-brew-2.md"
    assert first.read_text(encoding="utf-8").endswith("Body one\n")
    assert second.read_text(encoding="utf-8").endswith("Body two\n")
