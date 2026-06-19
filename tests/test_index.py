"""Tests for the embedding index: search ranking and link suggestions."""

from __future__ import annotations

from pathlib import Path

from brain.index import BrainIndex


def test_search_returns_ranked_results(vault: Path):
    index = BrainIndex.build(vault)

    hits = index.search("breakfast oats chia", top_k=3)

    assert hits, "expected at least one hit"
    # Scores must be sorted descending.
    assert hits == sorted(hits, key=lambda h: h.score, reverse=True)
    # The oats note should be the top match.
    assert hits[0].path == "notes/overnight-oats.md"
    assert hits[0].score > 0


def test_search_snippet_is_query_aware(vault: Path):
    index = BrainIndex.build(vault)

    hits = index.search("habit loop systems", top_k=1)

    assert hits
    assert "habit" in hits[0].snippet.lower() or "systems" in hits[0].snippet.lower()


def test_suggest_links_computes_relationships(vault: Path):
    index = BrainIndex.build(vault)

    suggestions = index.suggest_links()

    # Deep work and atomic habits share productivity/reading vocabulary, so they
    # should be suggested as related to each other.
    pairs = {(s.source_path, s.target_slug) for s in suggestions}
    assert any(
        target == "atomic-habits-notes" for _, target in pairs
    ), f"expected an atomic-habits link, got {pairs}"
    assert all(s.score > 0 for s in suggestions)


def test_index_roundtrips_to_disk(vault: Path, tmp_path: Path):
    index = BrainIndex.build(vault)
    index_path = tmp_path / "index.json"
    index.save(index_path)

    reloaded = BrainIndex.load(vault, index_path)

    assert reloaded.vectors == index.vectors
