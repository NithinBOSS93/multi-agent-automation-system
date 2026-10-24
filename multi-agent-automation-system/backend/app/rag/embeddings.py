"""Deterministic MD5 hash-based embeddings.

Why: HuggingFace model downloads were blocked on the network this project was
built on, so instead of a neural embedding model we use the "hashing trick":

1. Split text into word tokens and character trigrams.
2. MD5-hash each feature -> pick a bucket (index) and a sign (+1 / -1).
3. Add a TF weight to that bucket in a fixed-size vector.
4. L2-normalise so cosine similarity works.

Texts that share words/trigrams end up with similar vectors. It needs no
internet, no GPU and gives the same vector for the same text every time.
"""
import hashlib
import math
import re

from chromadb import Documents, EmbeddingFunction, Embeddings

from app.core.config import settings

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "be", "it", "this", "that", "with", "as", "by", "at", "from",
}


def _features(text: str) -> list[tuple[str, float]]:
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
    feats: list[tuple[str, float]] = [("w:" + w, 1.0) for w in words]
    # bigrams carry a bit of word order
    feats += [("b:" + a + "_" + b, 0.7) for a, b in zip(words, words[1:])]
    # trigrams make it tolerant to typos / word forms
    for w in words:
        padded = f"#{w}#"
        feats += [("c:" + padded[i:i + 3], 0.3) for i in range(len(padded) - 2)]
    return feats


def embed_text(text: str, dim: int | None = None) -> list[float]:
    dim = dim or settings.embedding_dim
    vec = [0.0] * dim
    for feat, weight in _features(text):
        digest = hashlib.md5(feat.encode()).digest()
        index = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[index] += sign * weight
    # sublinear scaling then L2 normalisation
    vec = [math.copysign(math.log1p(abs(v)), v) for v in vec]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class HashEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB-compatible embedding function."""

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 (chroma API name)
        return [embed_text(t, self.dim) for t in input]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are already unit length
