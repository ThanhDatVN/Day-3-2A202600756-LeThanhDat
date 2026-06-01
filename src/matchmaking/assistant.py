"""
AI Chat Assistant cho Volunteer (tình nguyện viên).

Trợ lý hỏi-đáp về dữ liệu hồ sơ & kết quả match: "ai chưa được ghép?",
"vì sao P01 hợp với P12?", "có bao nhiêu người ở Hà Nội?"...
Trả lời dựa HOÀN TOÀN trên dữ liệu được nạp (grounded), có fallback offline.
"""
from collections import Counter
from typing import Dict, Any, Optional

from src.matchmaking.llm import get_provider, chat
from src.telemetry.logger import logger

SYSTEM = ("Bạn là trợ lý cho tình nguyện viên vận hành chương trình mai mối. "
          "CHỈ trả lời dựa trên DỮ LIỆU được cung cấp (hồ sơ + kết quả gợi ý). "
          "Không bịa thông tin. Trả lời ngắn gọn, rõ ràng bằng tiếng Việt.")


class VolunteerAssistant:
    def __init__(self, matcher, chat_model: str = "gpt-4o-mini",
                 api_key: Optional[str] = None):
        self.matcher = matcher
        self.chat_model = chat_model
        self.provider = get_provider(chat_model, api_key)

    def _context(self) -> str:
        # Pre-computed facts so the LLM reads counts instead of (mis)counting them.
        cities = Counter(p["LOCATION"] for p in self.matcher.profiles)
        genders = Counter(p["GENDER"] for p in self.matcher.profiles)
        lines = [
            "THỐNG KÊ (đã tính sẵn, dùng số này):",
            "- Theo thành phố: " + "; ".join(f"{c}: {n}" for c, n in cities.items()),
            "- Theo giới tính: " + "; ".join(f"{g}: {n}" for g, n in genders.items()),
            "", "HỒ SƠ:",
        ]
        for p in self.matcher.profiles:
            lines.append(f"{p['ID']} {p['NAME']} | {p['GENDER']} {p['AGE']}t {p['LOCATION']} "
                         f"| sở thích: {p['HOBBIES']}")
        # Top-1 gợi ý mỗi người để trợ lý trả lời nhanh.
        lines.append("\nGỢI Ý (top-1 mỗi người):")
        topk = self.matcher.topk_all(k=1)
        for r in topk["results"]:
            c = r["candidates"][0] if r["candidates"] else None
            lines.append(f"{r['person']['id']} {r['person']['name']} → "
                         + (f"{c['name']} ({c['score']*100:.0f}%)" if c else "(không có)"))
        return "\n".join(lines)

    def ask(self, question: str) -> Dict[str, Any]:
        logger.log_event("VOLUNTEER_ASK", {"q": question})
        prompt = f"DỮ LIỆU:\n{self._context()}\n\nCâu hỏi của tình nguyện viên: {question}"
        answer = chat(self.provider, prompt, SYSTEM, self.chat_model, event="VOLUNTEER")
        if answer is None:
            answer = ("(offline) Mình cần API key để trả lời tự nhiên. "
                      "Tạm thời bạn xem dữ liệu hồ sơ ở tab Hồ sơ và bảng gợi ý nhé.")
        return {"question": question, "answer": answer}
