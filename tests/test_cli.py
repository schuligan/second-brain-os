"""End-to-end CLI tests via main(), exercising the approval gate."""

from __future__ import annotations

import os
from pathlib import Path

from brain.cli import main


def _run(args: list[str], vault: Path) -> int:
    os.environ.pop("ANTHROPIC_API_KEY", None)  # force mock mode
    return main(["--vault", str(vault), *args])


def test_index_command_builds_index(vault: Path, capsys):
    code = _run(["index"], vault)
    out = capsys.readouterr().out

    assert code == 0
    assert "Indexed" in out
    assert (vault / ".brain" / "index.json").exists()


def test_search_command_returns_results(vault: Path, capsys):
    _run(["index"], vault)
    code = _run(["search", "habit", "systems"], vault)
    out = capsys.readouterr().out

    assert code == 0
    assert "atomic-habits-notes.md" in out


def test_capture_without_yes_writes_nothing(vault: Path, capsys):
    # Non-interactive shell + no --yes => approval gate blocks the write.
    code = _run(["capture", "A note about baking sourdough bread"], vault)
    out = capsys.readouterr().out

    assert code == 0
    assert "Skipped" in out
    # No new note in notes/.
    assert not any("sourdough" in p.name for p in (vault / "notes").glob("*.md"))


def test_capture_with_yes_files_note(vault: Path, capsys):
    code = _run(["capture", "--yes", "A note about baking sourdough bread"], vault)
    out = capsys.readouterr().out

    assert code == 0
    assert "Filed" in out
    assert any("sourdough" in p.name for p in (vault / "notes").glob("*.md"))


def test_daily_preview_does_not_write(vault: Path, capsys):
    _run(["index"], vault)
    code = _run(["daily"], vault)

    assert code == 0
    # Preview only: no file written without --write.
    assert not list((vault / "daily").glob("*.md"))


def test_daily_write_with_yes_saves(vault: Path, capsys):
    code = _run(["daily", "--write", "--yes"], vault)
    out = capsys.readouterr().out

    assert code == 0
    assert "Wrote" in out
    assert list((vault / "daily").glob("*.md"))
