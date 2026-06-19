"""Deterministic, offline hashing embedder + cosine similarity.

This is a "hashing trick" / bag-of-words embedder: every token is hashed into a
fixed-dimension vector. It needs no model download and no network, so search and
linking work identically in CI, in mock mode, and on a plane. It is not as smart
as a transformer embedding, but it is fully deterministic and good enough to
demonstrate ranked retrieval and similarity-based linking.
"""

from __future__ import annotations

import hashlib
import math
import re

EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Very small English stoplist so common words do not dominate similarity.
_STOPWORDS = frozenset(
    """a an and are as at be by для for from has have in into is it its of on or
    that the their them this to was were will with you your i""".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords removed, length >= 2."""
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= 2 and tok not in _STOPWORDS
    ]


def _bucket(token: str) -> int:
    """Stable hash of a token into [0, EMBED_DIM). Uses blake2b for determinism."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % EMBED_DIM


def embed(text: str) -> list[float]:
    """Return an L2-normalized hashed bag-of-words vector for the text."""
    vec = [0.0] * EMBED_DIM
    for token in tokenize(text):
        vec[_bucket(token)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors (already L2-normalized)."""
    return sum(x * y for x, y in zip(a, b, strict=True))
