"""
Core matchmaking engine — MULTI-LAYER scoring + Top-K (no LLM reasoning loop).

Pipeline (mirrors README2.md):
  1. Read profiles from the CSV that simulates the Google Sheet.
  2. Normalize text (e.g. "HN" / "hà nội" -> "HÀ NỘI").
  3. Score each candidate with a WEIGHTED, MULTI-LAYER score:
        - hard filter : opposite gender (must pass)
        - semantic    : embedding cosine on hobbies+wishes      (weight 0.55)
        - hobbies     : keyword Jaccard overlap                  (weight 0.20)
        - location    : same normalized city bonus               (weight 0.15)
        - age         : age proximity                            (weight 0.10)
  4. Return TOP-K candidates per person (not a single 1-1 pairing).
  5. Export to data/matches.csv + matches.json (the "new sheet").
"""
import os
import re
import csv
import json
from typing import List, Dict, Any, Optional

from src.core.embeddings import SimilarityEngine

# Layer weights (sum = 1.0). Tunable — exposed in the match report.
WEIGHTS = {"semantic": 0.55, "hobbies": 0.20, "location": 0.15, "age": 0.10}
MAX_AGE_GAP = 10  # years; beyond this the age layer contributes 0

_LOCATION_ALIASES = {
    "hn": "HÀ NỘI", "ha noi": "HÀ NỘI", "hà nội": "HÀ NỘI", "hanoi": "HÀ NỘI",
    "sg": "TP HCM", "tphcm": "TP HCM", "tp hcm": "TP HCM", "tp.hcm": "TP HCM",
    "sài gòn": "TP HCM", "sai gon": "TP HCM", "hồ chí minh": "TP HCM", "ho chi minh": "TP HCM",
    "đn": "ĐÀ NẴNG", "dn": "ĐÀ NẴNG", "da nang": "ĐÀ NẴNG", "đà nẵng": "ĐÀ NẴNG",
}


def normalize_location(value: str) -> str:
    key = (value or "").strip().lower()
    return _LOCATION_ALIASES.get(key, (value or "").strip().upper())


def profile_text(p: Dict[str, Any]) -> str:
    return f"{p.get('HOBBIES', '')}. {p.get('LOOKING_FOR', '')}"


class Matchmaker:
    def __init__(self, csv_path: str = "data/profiles.csv",
                 api_key: Optional[str] = None,
                 embed_model: str = "text-embedding-3-small"):
        self.csv_path = csv_path
        self.profiles: List[Dict[str, Any]] = self._load(csv_path)
        self.index = {p["ID"]: i for i, p in enumerate(self.profiles)}
        self.engine = SimilarityEngine(api_key=api_key, model=embed_model)
        self.mode = self.engine.fit([profile_text(p) for p in self.profiles])

    # ------------------------------------------------------------------ load
    @staticmethod
    def _load(path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Profiles sheet not found: {path}")
        rows = []
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                r = {k.strip().upper(): (v.strip() if v else "") for k, v in r.items()}
                r["AGE"] = int(r["AGE"]) if str(r.get("AGE", "")).isdigit() else 0
                r["LOCATION"] = normalize_location(r.get("LOCATION", ""))
                rows.append(r)
        return rows

    def get(self, profile_id: str) -> Optional[Dict[str, Any]]:
        i = self.index.get((profile_id or "").upper())
        return self.profiles[i] if i is not None else None

    # ------------------------------------------------------------- scoring
    @staticmethod
    def _opposite(gender: str) -> str:
        return "NỮ" if gender.upper() == "NAM" else "NAM"

    def _score(self, i: int, j: int) -> Dict[str, Any]:
        """Multi-layer weighted score with a transparent breakdown."""
        pa, pb = self.profiles[i], self.profiles[j]
        semantic = self.engine.sim(i, j)
        hobbies = self.engine.jaccard(i, j)
        location = 1.0 if pa["LOCATION"] == pb["LOCATION"] else 0.0
        age = max(0.0, 1.0 - abs(pa["AGE"] - pb["AGE"]) / MAX_AGE_GAP)
        total = (WEIGHTS["semantic"] * semantic + WEIGHTS["hobbies"] * hobbies +
                 WEIGHTS["location"] * location + WEIGHTS["age"] * age)
        return {
            "total": round(total, 4),
            "breakdown": {
                "semantic": round(semantic, 3),
                "hobbies": round(hobbies, 3),
                "location": location,
                "age": round(age, 3),
            },
        }

    def _reason(self, i: int, j: int, breakdown: Dict[str, float]) -> str:
        pa, pb = self.profiles[i], self.profiles[j]
        shared_tokens = set(self.engine.shared_terms(i, j))
        items = [s.strip() for s in (pa["HOBBIES"] + "," + pb["HOBBIES"]).split(",") if s.strip()]
        shared_items = []
        for it in items:
            toks = set(re.findall(r"\w+", it.lower(), flags=re.UNICODE))
            if toks & shared_tokens and it.lower() not in [s.lower() for s in shared_items]:
                shared_items.append(it)
        bits = []
        if shared_items:
            bits.append("cùng quan tâm: " + ", ".join(shared_items[:3]))
        if breakdown["location"]:
            bits.append(f"cùng ở {pa['LOCATION']}")
        if breakdown["age"] >= 0.8:
            bits.append("tuổi tương đồng")
        return "; ".join(bits) if bits else "gu sống & mong muốn tương đồng"

    # --------------------------------------------------------------- queries
    def _candidate(self, i: int, j: int) -> Dict[str, Any]:
        sc = self._score(i, j)
        p = self.profiles[j]
        return {
            "id": p["ID"], "name": p["NAME"], "age": p["AGE"], "gender": p["GENDER"],
            "location": p["LOCATION"], "hobbies": p["HOBBIES"],
            "score": sc["total"], "breakdown": sc["breakdown"],
            "reason": self._reason(i, j, sc["breakdown"]),
        }

    def find_topk(self, profile_id: str, k: int = 3) -> Dict[str, Any]:
        """Top-K opposite-gender candidates for one person, multi-layer ranked."""
        i = self.index.get((profile_id or "").upper())
        if i is None:
            return {"error": f"Không tìm thấy hồ sơ '{profile_id}'."}
        want = self._opposite(self.profiles[i]["GENDER"])
        cands = [self._candidate(i, j) for j, c in enumerate(self.profiles)
                 if j != i and c["GENDER"].upper() == want]
        cands.sort(key=lambda c: c["score"], reverse=True)
        return {"target": self._brief(self.profiles[i]),
                "candidates": cands[:k], "mode": self.mode, "weights": WEIGHTS}

    def topk_all(self, k: int = 3) -> Dict[str, Any]:
        """For EVERY person: their Top-K suggestions (not a 1-1 assignment)."""
        results = []
        for p in self.profiles:
            r = self.find_topk(p["ID"], k=k)
            results.append({"person": self._brief(p), "candidates": r["candidates"]})
        return {
            "results": results,
            "stats": {"total_profiles": len(self.profiles), "k": k,
                      "similarity_mode": self.mode},
            "weights": WEIGHTS,
        }

    def greedy_pairs(self) -> Dict[str, Any]:
        """Overview only: one best 1-1 assignment (used in the report header)."""
        n = len(self.profiles)
        scored = []
        for i in range(n):
            for j in range(i + 1, n):
                if self.profiles[i]["GENDER"].upper() == self.profiles[j]["GENDER"].upper():
                    continue
                sc = self._score(i, j)
                scored.append((sc["total"], i, j, sc["breakdown"]))
        scored.sort(reverse=True, key=lambda t: t[0])
        used, pairs = set(), []
        for total, i, j, bd in scored:
            if i in used or j in used:
                continue
            used.update((i, j))
            pairs.append({"a": self._brief(self.profiles[i]), "b": self._brief(self.profiles[j]),
                          "score": round(total, 4), "reason": self._reason(i, j, bd)})
        unmatched = [self._brief(p) for k, p in enumerate(self.profiles) if k not in used]
        return {"pairs": pairs, "unmatched": unmatched,
                "stats": {"total_profiles": n, "matched_pairs": len(pairs),
                          "unmatched": len(unmatched), "similarity_mode": self.mode}}

    @staticmethod
    def _brief(p: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": p["ID"], "name": p["NAME"], "age": p["AGE"], "gender": p["GENDER"],
                "location": p["LOCATION"], "hobbies": p["HOBBIES"],
                "email": p.get("EMAIL", ""), "zalo": p.get("ZALO", "")}

    # ---------------------------------------------------------------- export
    def export(self, topk: Dict[str, Any], out_dir: str = "data") -> Dict[str, str]:
        """Write Top-K results to disk (simulating 'export to a new sheet')."""
        os.makedirs(out_dir, exist_ok=True)
        json_path = os.path.join(out_dir, "matches.json")
        csv_path = os.path.join(out_dir, "matches.csv")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(topk, f, ensure_ascii=False, indent=2)
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["PERSON_ID", "PERSON_NAME", "RANK", "MATCH_ID", "MATCH_NAME",
                        "SCORE", "REASON"])
            for r in topk.get("results", []):
                for rank, c in enumerate(r["candidates"], 1):
                    w.writerow([r["person"]["id"], r["person"]["name"], rank,
                                c["id"], c["name"], c["score"], c["reason"]])
        return {"json": json_path, "csv": csv_path}
