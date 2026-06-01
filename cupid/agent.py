"""
Agent điều phối: ngôn ngữ tự nhiên → trích xuất → tính tương thích → top-5 →
đánh giá AI → trả về. Hỗ trợ từ chối & hàng đợi.
"""
import json
from typing import Dict, Any, List, Optional

from cupid import config, extractor, compatibility, evaluator, waitlist, llm


def load_people() -> List[Dict[str, Any]]:
    with open(config.PEOPLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def process(nl_text: str, exclude_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Xử lý mô tả người dùng → trả hồ sơ trích xuất + top-5 kèm đánh giá."""
    llm.log("AGENT_START", {"input": nl_text[:200]})
    user = extractor.extract(nl_text)
    user["id"] = "ME"

    # Khi có người dùng mới: kiểm tra hàng đợi xem ai đang chờ mà hợp với người này.
    waitlist_hits = waitlist.check_new_user(user)

    people = [p for p in load_people() if p["id"] not in (exclude_ids or [])]
    top = compatibility.top_k(user, people, k=config.TOP_K)
    evals = evaluator.evaluate(user, top)
    for c in top:
        c.update(evals.get(c["id"], {"label": "", "assessment": "", "advice": ""}))

    llm.log("AGENT_END", {"user": user.get("name"), "n_candidates": len(top),
                          "waitlist_hits": len(waitlist_hits)})
    return {"profile": user, "candidates": top, "waitlist_hits": waitlist_hits}


def reject_and_wait(user: Dict[str, Any], rejected_ids: List[str]) -> Dict[str, Any]:
    """Người dùng từ chối hết → lưu vào hàng đợi đến khi có người phù hợp tiếp theo."""
    return waitlist.add(user, rejected_ids)


def accept(candidate_id: str) -> Dict[str, Any]:
    """Người dùng ĐỒNG Ý với một đối tượng → trả về SĐT để liên hệ."""
    for p in load_people():
        if p["id"] == candidate_id:
            llm.log("ACCEPT", {"candidate_id": candidate_id, "name": p["name"]})
            return {"matched": True, "id": p["id"], "name": p["name"],
                    "phone": p.get("phone", ""),
                    "message": f"Bạn và {p['name']} đã được kết nối! "
                               f"Liên hệ qua SĐT: {p.get('phone','(chưa có)')}"}
    return {"matched": False, "error": f"Không tìm thấy đối tượng '{candidate_id}'."}
