"""Tests for the agentic flows: capture classification, approval-gated filing,
and daily-note synthesis. All run in mock mode with no network."""

from __future__ import annotations

from pathlib import Path

from brain.agent import capture_classify, capture_file, synthesize_daily
from brain.config import Config
from brain.index import BrainIndex
from brain.llm import MockLLM, get_llm


def test_get_llm_defaults_to_mock_without_key(config: Config):
    assert config.is_mock
    assert isinstance(get_llm(config), MockLLM)


def test_capture_classify_does_not_write(vault: Path, config: Config):
    index = BrainIndex.build(vault)
    before = {p.name for p in (vault / "references").glob("*.md")}

    plan = capture_classify(
        "Finished reading a great book on building better habits", index, MockLLM()
    )

    after = {p.name for p in (vault / "references").glob("*.md")}
    # classify must be side-effect free — approval gating happens in the CLI.
    assert before == after
    assert plan.classification.folder == "references"
    assert "reading" in plan.classification.tags


def test_capture_file_requires_explicit_commit(vault: Path, config: Config):
    index = BrainIndex.build(vault)
    plan = capture_classify(
        "Recipe idea: roast carrots with cumin and a yogurt drizzle", index, MockLLM()
    )

    # Only now, after an explicit call, is anything written.
    path = capture_file(plan, config)

    assert path.exists()
    assert path.parent.name == "references"  # "recipe" -> references folder
    content = path.read_text(encoding="utf-8")
    assert "title:" in content
    assert "cumin" in content


def test_capture_file_does_not_overwrite(vault: Path, config: Config):
    index = BrainIndex.build(vault)
    plan = capture_classify("A quick note about cooking pasta", index, MockLLM())

    first = capture_file(plan, config)
    second = capture_file(plan, config)

    assert first != second  # second write gets a -2 suffix


def test_capture_links_to_related_notes(vault: Path, config: Config):
    index = BrainIndex.build(vault)

    plan = capture_classify(
        "Thinking more about my deep work focus blocks and routines", index, MockLLM()
    )

    # The body should reference a related existing note via a wikilink.
    assert "[[" in plan.body


def test_synthesize_daily_generates_sections(vault: Path):
    index = BrainIndex.build(vault)

    frontmatter, body = synthesize_daily(index, lookback_days=3650)

    assert frontmatter.tags == ["daily"]
    assert "## Recent captures" in body
    assert "## Open projects" in body
    # The trailmix project note should appear under open projects.
    assert "trailmix-app-idea" in body
