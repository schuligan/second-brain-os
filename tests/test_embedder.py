"""Unit tests for the deterministic hashing embedder."""

from __future__ import annotations

from brain.embedder import EMBED_DIM, cosine, embed, tokenize


def test_embed_is_deterministic():
    # Arrange
    text = "overnight oats with chia seeds"

    # Act
    first = embed(text)
    second = embed(text)

    # Assert
    assert first == second
    assert len(first) == EMBED_DIM


def test_embed_is_l2_normalized():
    # Act
    vec = embed("deep work routine focus blocks")

    # Assert
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_cosine_of_identical_text_is_one():
    # Arrange
    vec = embed("habit loop cue craving reward")

    # Act / Assert
    assert abs(cosine(vec, vec) - 1.0) < 1e-9


def test_related_text_scores_higher_than_unrelated():
    # Arrange
    base = embed("sourdough bread baking hydration fermentation")
    related = embed("baking bread with a sourdough starter")
    unrelated = embed("offline hiking gps waypoint alerts")

    # Act
    related_score = cosine(base, related)
    unrelated_score = cosine(base, unrelated)

    # Assert
    assert related_score > unrelated_score


def test_tokenize_drops_stopwords_and_short_tokens():
    # Act
    tokens = tokenize("The a I of cooking recipe")

    # Assert
    assert "cooking" in tokens
    assert "recipe" in tokens
    assert "the" not in tokens
    assert "a" not in tokens
