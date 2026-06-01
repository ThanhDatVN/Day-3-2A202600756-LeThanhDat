"""
Hàng đợi (database đơn giản bằng JSON).

Khi người dùng thấy các gợi ý đều KHÔNG phù hợp và chọn "chờ người tiếp theo",
hồ sơ của họ được lưu vào hàng đợi. Mỗi khi có NGƯỜI DÙNG MỚI vào hệ thống, ta
kiểm tra hàng đợi: ai đang chờ mà hợp với người mới (điểm ≥ ngưỡng) thì được
"ghép" và lấy ra khỏi hàng đợi.
"""
import os
import json
from typing import List, Dict, Any

from cupid import config, compatibility, llm


def _load() -> List[Dict[str, Any]]:
    if not os.path.exists(config.WAITLIST_PATH):
        return []
    try:
        with open(config.WAITLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(config.WAITLIST_PATH) or ".", exist_ok=True)
    with open(config.WAITLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add(user: Dict[str, Any], rejected_ids: List[str] = None) -> Dict[str, Any]:
    items = _load()
    record = {**user, "rejected": rejected_ids or []}
    items.append(record)
    _save(items)
    llm.log("WAITLIST_ADD", {"name": user.get("name"), "size": len(items)})
    return {"queued": True, "size": len(items)}


def list_all() -> List[Dict[str, Any]]:
    return _load()


def check_new_user(new_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tìm người đang chờ mà hợp với người mới → ghép & lấy khỏi hàng đợi."""
    waiters = _load()
    if not waiters:
        return []
    hits, remaining = [], []
    for w in waiters:
        score = compatibility.pair_score(new_user, w)
        if score >= config.MATCH_THRESHOLD and new_user.get("name") not in w.get("rejected", []):
            hits.append({"waiter": w, "score": score})
        else:
            remaining.append(w)
    if hits:
        _save(remaining)  # những người đã được ghép thì rời hàng đợi
        llm.log("WAITLIST_MATCH", {"new_user": new_user.get("name"),
                                   "matched": [h["waiter"].get("name") for h in hits]})
    return hits
