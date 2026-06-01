"""
AI Review dữ liệu TRƯỚC khi match.

Kết hợp 2 lớp:
  1. Rule-based: phát hiện lỗi cứng (thiếu trường, tuổi bất thường, trùng email,
     giới tính lạ, sở thích quá ngắn).
  2. AI note (LLM): nhận xét tổng quan chất lượng dữ liệu bằng tiếng Việt
     (có fallback nếu không có API key).
"""
import re
from collections import Counter
from typing import List, Dict, Any, Optional

from src.matchmaking.llm import get_provider, chat
from src.telemetry.logger import logger

REQUIRED = ["NAME", "AGE", "GENDER", "HOBBIES"]
VALID_GENDERS = {"NAM", "NỮ"}

SYSTEM = ("Bạn là chuyên viên kiểm duyệt dữ liệu cho chương trình mai mối. "
          "Nhận xét NGẮN GỌN (3-4 câu) bằng tiếng Việt về chất lượng dữ liệu hồ sơ: "
          "mức độ đầy đủ, điểm cần làm sạch, có nên match hay không.")


def review(profiles: List[Dict[str, Any]],
           chat_model: str = "gpt-4o-mini",
           api_key: Optional[str] = None) -> Dict[str, Any]:
    issues = []
    emails = Counter(p.get("EMAIL", "").lower() for p in profiles if p.get("EMAIL"))

    for p in profiles:
        pid = p.get("ID", "?")
        for field in REQUIRED:
            if not str(p.get(field, "")).strip():
                issues.append({"id": pid, "severity": "error",
                               "message": f"Thiếu trường {field}"})
        age = p.get("AGE", 0)
        if not (18 <= age <= 80):
            issues.append({"id": pid, "severity": "warn",
                           "message": f"Tuổi bất thường: {age}"})
        if p.get("GENDER", "").upper() not in VALID_GENDERS:
            issues.append({"id": pid, "severity": "warn",
                           "message": f"Giới tính lạ: '{p.get('GENDER')}'"})
        hob = [h for h in (p.get("HOBBIES", "") or "").split(",") if h.strip()]
        if len(hob) < 2:
            issues.append({"id": pid, "severity": "warn",
                           "message": "Sở thích quá ít (<2 mục) → match kém chính xác"})
        if p.get("EMAIL") and emails[p["EMAIL"].lower()] > 1:
            issues.append({"id": pid, "severity": "error",
                           "message": f"Email trùng: {p['EMAIL']}"})

    errors = sum(1 for i in issues if i["severity"] == "error")
    warns = sum(1 for i in issues if i["severity"] == "warn")
    ready = errors == 0

    # AI overall note (optional)
    provider = get_provider(chat_model, api_key)
    summary = (f"{len(profiles)} hồ sơ; {errors} lỗi, {warns} cảnh báo. "
               f"Đầy đủ trường bắt buộc: {len(profiles) - len({i['id'] for i in issues if i['severity']=='error'})}/{len(profiles)}.")
    ai_note = chat(provider,
                   f"Tóm tắt dữ liệu: {summary}\nMột vài vấn đề: "
                   + "; ".join(f"{i['id']}:{i['message']}" for i in issues[:8]),
                   SYSTEM, chat_model, event="DATA_REVIEW")
    if ai_note is None:
        ai_note = ("(offline) " + ("Dữ liệu sẵn sàng để match." if ready
                   else "Cần xử lý các lỗi nghiêm trọng trước khi match."))

    logger.log_event("DATA_REVIEW_DONE", {"errors": errors, "warns": warns, "ready": ready})
    return {"ready_to_match": ready, "errors": errors, "warnings": warns,
            "issues": issues, "summary": summary, "ai_note": ai_note}
