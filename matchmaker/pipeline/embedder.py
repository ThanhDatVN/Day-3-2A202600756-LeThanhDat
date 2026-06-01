"""
Embedding per-field (interests / values / lifestyle) → similarity có breakdown.

Tái sử dụng SimilarityEngine (OpenAI embeddings + fallback offline). Mỗi trường
được embed riêng để compute_similarity trả về detail từng khía cạnh.
"""
from typing import List, Dict, Any, Optional

from src.core.embeddings import SimilarityEngine

FIELDS = ["interests", "values", "lifestyle"]
FIELD_WEIGHTS = {"interests": 0.5, "values": 0.3, "lifestyle": 0.2}


class Embedder:
    def __init__(self, profiles: List[Dict[str, Any]],
                 api_key: Optional[str] = None,
                 model: str = "text-embedding-3-small"):
        self.idx = {p["id"]: i for i, p in enumerate(profiles)}
        self.engines: Dict[str, SimilarityEngine] = {}
        self.mode = "offline"
        for f in FIELDS:
            eng = SimilarityEngine(api_key=api_key, model=model)
            self.mode = eng.fit([p.get(f, "") for p in profiles])
            self.engines[f] = eng

    def similarity(self, id_a: str, id_b: str) -> Dict[str, Any]:
        i, j = self.idx[id_a], self.idx[id_b]
        detail = {f: round(self.engines[f].sim(i, j), 3) for f in FIELDS}
        score = sum(FIELD_WEIGHTS[f] * detail[f] for f in FIELDS)
        return {"score": round(score, 3), "detail": detail}
