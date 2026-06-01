"""
Đẩy top-K lên OpenAI để nhận ĐÁNH GIÁ độ phù hợp + LỜI KHUYÊN cho từng đối tượng.
"""
import json
from typing import List, Dict, Any

from cupid import llm

SYSTEM = """Bạn là chuyên gia tư vấn hẹn hò. Với mỗi ứng viên được cung cấp, hãy:
- đánh giá ngắn gọn vì sao phù hợp/chưa phù hợp với người dùng (1-2 câu),
- đưa 1 lời khuyên thực tế để kết nối (cách bắt chuyện / ý tưởng hẹn).
Trả về DUY NHẤT JSON dạng:
{"results":[{"id": "...", "label": "Rất hợp|Khá hợp|Có thể thử", "assessment": "...", "advice": "..."}]}
Trả lời bằng tiếng Việt, súc tích."""


def evaluate(user: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    if not candidates:
        return {}
    u = (f"Người dùng: {user.get('name','')}, {user.get('age','')} tuổi, "
         f"{user.get('gender','')}, {user.get('address','')}. "
         f"Sở thích: {user.get('hobbies','')}. Mong muốn: {user.get('requirements','')}.")
    cand_lines = [
        f"- id {c['id']}: {c['name']}, {c['age']} tuổi, {c['gender']}, {c['address']}, "
        f"sở thích: {c['hobbies']}, mong muốn: {c['requirements']} (điểm hệ thống {c['score']})"
        for c in candidates]
    user_msg = u + "\n\nDanh sách ứng viên:\n" + "\n".join(cand_lines)

    data = llm.chat_json(SYSTEM, user_msg)
    out = {}
    for r in data.get("results", []):
        if "id" in r:
            out[r["id"]] = {"label": r.get("label", ""),
                            "assessment": r.get("assessment", ""),
                            "advice": r.get("advice", "")}
    llm.log("EVALUATE", {"user": user.get("name"), "n": len(candidates)})
    return out
