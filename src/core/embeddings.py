"""
Similarity engine for matchmaking.

Primary mode: OpenAI embeddings (text-embedding-3-small) + cosine similarity —
this is what lets "leo núi" and "trekking" score as similar even though the words
differ (deeper than word-by-word matching).

Fallback mode: if there is no API key / the call fails, we degrade gracefully to
an offline token Jaccard similarity so the demo still runs.
"""
import os
import re
import math
from typing import List, Optional

try:
    from openai import OpenAI
except ImportError:  # openai not installed
    OpenAI = None

_STOPWORDS = {
    "và", "người", "thích", "tìm", "có", "một", "những", "rất", "cùng",
    "the", "a", "tại", "cho", "với", "là", "ở",
}


def _tokens(text: str) -> set:
    toks = re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE)
    return {t for t in toks if t not in _STOPWORDS and len(t) > 1}


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SimilarityEngine:
    """Fit a corpus of texts once, then query pairwise similarity by index."""

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "text-embedding-3-small"):
        self.model = model
        self.mode = "offline"
        self.client = None
        self.vectors: Optional[List[List[float]]] = None
        self.token_sets: Optional[List[set]] = None

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key and OpenAI is not None and not re.search(r"x{4,}", api_key):
            try:
                self.client = OpenAI(api_key=api_key)
                self.mode = "openai"
            except Exception:
                self.mode = "offline"

    def fit(self, texts: List[str]) -> str:
        """Embed/index the corpus. Returns the effective mode actually used."""
        # Always keep token sets so we can explain matches by shared keywords.
        self.token_sets = [_tokens(t) for t in texts]
        if self.mode == "openai":
            try:
                resp = self.client.embeddings.create(model=self.model, input=texts)
                self.vectors = [d.embedding for d in resp.data]
                return "openai"
            except Exception:
                self.mode = "offline"  # fall through to offline
        return "offline"

    def sim(self, i: int, j: int) -> float:
        """Similarity in [0, 1] between corpus items i and j."""
        if self.mode == "openai" and self.vectors is not None:
            # cosine for embeddings is in [-1, 1]; clamp negatives to 0.
            return max(0.0, _cosine(self.vectors[i], self.vectors[j]))
        a, b = self.token_sets[i], self.token_sets[j]
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def shared_terms(self, i: int, j: int) -> List[str]:
        """Overlapping keywords (used to explain a match)."""
        if not self.token_sets:
            return []
        return sorted(self.token_sets[i] & self.token_sets[j])

    def jaccard(self, i: int, j: int) -> float:
        """Token Jaccard overlap in [0, 1] (a 'shared hobbies' signal)."""
        if not self.token_sets:
            return 0.0
        a, b = self.token_sets[i], self.token_sets[j]
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)
