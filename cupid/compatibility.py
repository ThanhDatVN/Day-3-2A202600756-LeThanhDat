"""
Hàm tính độ tương thích (đa tầng) giữa người dùng và các đối tượng.

Lọc CỨNG: chỉ ghép khác giới (mặc định dị tính).
Tầng điểm mềm (tổng = 1.0):
  - semantic   : embedding cosine giữa (sở thích+yêu cầu) hai bên   (0.50)
  - req_match  : yêu cầu của user khớp hồ sơ đối phương             (0.20)
  - age        : độ gần tuổi                                        (0.12)
  - address    : cùng tỉnh/thành                                    (0.18)
"""
import math
from typing import List, Dict, Any

from cupid import llm

WEIGHTS = {"semantic": 0.50, "req": 0.20, "age": 0.12, "address": 0.18}
MAX_AGE_GAP = 15


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _profile_text(p: Dict[str, Any]) -> str:
    return f"Sở thích: {p.get('hobbies','')}. Mong muốn: {p.get('requirements','')}"


def _norm_gender(g: str) -> str:
    g = (g or "").strip().lower()
    if g in ("nam", "male"):
        return "Nam"
    if g in ("nữ", "nu", "female"):
        return "Nữ"
    return ""


def _opposite_gender(a: str, b: str) -> bool:
    """True nếu khác giới (hoặc thiếu thông tin giới tính → cho qua)."""
    ga, gb = _norm_gender(a), _norm_gender(b)
    if not ga or not gb:
        return True
    return ga != gb


def _factor_scores(user, cand, sem, req):
    if user.get("age") and cand.get("age"):
        age = max(0.0, 1.0 - abs(user["age"] - cand["age"]) / MAX_AGE_GAP)
    else:
        age = 0.5
    addr = 1.0 if (user.get("address", "").strip().lower() ==
                   cand.get("address", "").strip().lower() and user.get("address")) else 0.0
    total = (WEIGHTS["semantic"] * sem + WEIGHTS["req"] * req +
             WEIGHTS["age"] * age + WEIGHTS["address"] * addr)
    return total, {"semantic": round(sem, 3), "req_match": round(req, 3),
                   "age": round(age, 3), "address": addr}


def top_k(user: Dict[str, Any], people: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
    """Xếp hạng toàn bộ `people` theo độ tương thích với `user`, trả top-k."""
    # Lọc cứng: chỉ giữ ứng viên khác giới với user.
    people = [p for p in people if _opposite_gender(user.get("gender"), p.get("gender"))]
    if not people:
        return []
    user_all = _profile_text(user)
    user_req = user.get("requirements", "") or user_all
    texts = [user_all, user_req] + [_profile_text(p) for p in people]
    vecs = llm.embed(texts)
    uv, urv, pvs = vecs[0], vecs[1], vecs[2:]

    scored = []
    for p, pv in zip(people, pvs):
        sem = _cosine(uv, pv)
        req = _cosine(urv, pv)
        total, bd = _factor_scores(user, p, sem, req)
        # Ẩn SĐT trong kết quả gợi ý — chỉ lộ khi người dùng bấm "Đồng ý".
        public = {key: val for key, val in p.items() if key != "phone"}
        scored.append({**public, "score": round(total, 4), "breakdown": bd})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:k]


def pair_score(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """Điểm tương thích 1-1 (dùng cho hàng đợi). Khác giới mới tính."""
    if not _opposite_gender(a.get("gender"), b.get("gender")):
        return 0.0
    va, vb = llm.embed([_profile_text(a), _profile_text(b)])
    sem = _cosine(va, vb)
    total, _ = _factor_scores(a, b, sem, sem)
    return round(total, 4)
