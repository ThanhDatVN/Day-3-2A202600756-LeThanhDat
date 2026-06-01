"""
Thuật toán ghép chính: Gale-Shapley (ổn định, nam ngỏ lời).

Bản này CHẠY BẢO THỦ - chỉ chấp nhận ứng viên CÙNG THÀNH PHỐ và qua ràng buộc
cứng. Nhờ vậy nó ghép nhanh phần lớn "case dễ" và CHỪA LẠI nhóm "case khó"
(người không có ứng viên cùng thành phố) cho ReAct Agent xử lý.
"""
from typing import Dict, Any, List

from matchmaker.pipeline.store import ProfileStore


def _acceptable(store: ProfileStore, a_id: str, b_id: str) -> bool:
    a, b = store.get(a_id), store.get(b_id)
    if a["location"] != b["location"]:          # bảo thủ: chỉ cùng thành phố
        return False
    return store.check_hard_constraints(a_id, b_id)["passed"]


def gale_shapley(store: ProfileStore) -> Dict[str, Any]:
    males = [p["id"] for p in store.profiles.values() if p["gender"] == "male"]
    females = [p["id"] for p in store.profiles.values() if p["gender"] == "female"]

    # Danh sách ưu tiên = ứng viên chấp nhận được, xếp theo similarity giảm dần.
    def prefs(pid, others):
        ok = [o for o in others if _acceptable(store, pid, o)]
        ok.sort(key=lambda o: store.similarity(pid, o)["score"], reverse=True)
        return ok

    male_prefs = {m: prefs(m, females) for m in males}
    female_rank = {}
    for f in females:
        ranked = prefs(f, males)
        female_rank[f] = {m: r for r, m in enumerate(ranked)}  # nhỏ hơn = thích hơn

    free = [m for m in males if male_prefs[m]]
    next_idx = {m: 0 for m in males}
    engaged = {}  # female_id -> male_id

    while free:
        m = free.pop(0)
        if next_idx[m] >= len(male_prefs[m]):
            continue
        f = male_prefs[m][next_idx[m]]
        next_idx[m] += 1
        if f not in female_rank or m not in female_rank[f]:
            free.append(m)              # nữ này không chấp nhận m
            continue
        cur = engaged.get(f)
        if cur is None:
            engaged[f] = m
        elif female_rank[f][m] < female_rank[f][cur]:
            engaged[f] = m
            free.append(cur)
        else:
            free.append(m)

    matches = [{"a": m, "b": f} for f, m in engaged.items()]
    matched_ids = set(engaged.values()) | set(engaged.keys())
    unmatched = [pid for pid in store.profiles if pid not in matched_ids]
    return {"matches": matches, "matched_ids": matched_ids, "unmatched": unmatched}
