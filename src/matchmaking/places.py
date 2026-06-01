"""
Gợi ý địa điểm hẹn hò tự động cho một cặp.

Dùng LLM (theo thành phố + sở thích chung) để gợi ý 3 chỗ hẹn; có fallback
offline bằng "thư viện gợi ý" theo thành phố/sở thích khi không có API key.
"""
import re
from typing import Dict, Any, Optional

from src.matchmaking.llm import get_provider, chat

SYSTEM = ("Bạn là trợ lý hẹn hò. Gợi ý 3 ĐỊA ĐIỂM hẹn hò cụ thể, phù hợp với "
          "thành phố và sở thích chung của cặp đôi. Mỗi gợi ý 1 dòng, ngắn gọn, "
          "có lý do. Trả lời bằng tiếng Việt.")

# Fallback library: city -> theme keyword -> suggestion
_LIB = {
    "HÀ NỘI": {
        "cà phê": "Cà phê sách Tranquil (Nguyễn Quang Bích) - không gian yên tĩnh để trò chuyện",
        "sách": "Phố sách 19/12 - dạo và chọn sách cùng nhau",
        "leo": "Leo núi Hàm Lợn (Sóc Sơn) - trekking nửa ngày gần Hà Nội",
        "ảnh": "Phố cổ & Hồ Gươm - đi dạo chụp ảnh buổi sáng",
        "_default": "Hồ Tây - đạp xe ngắm hoàng hôn",
    },
    "TP HCM": {
        "gym": "Lớp leo núi trong nhà VietClimb (Q.Bình Thạnh) - vận động cùng nhau",
        "ẩm thực": "Phố ẩm thực Vĩnh Khánh (Q.4) - thử nhiều món",
        "cà phê": "The Workshop Coffee - cà phê specialty đúng gu",
        "_default": "Phố đi bộ Nguyễn Huệ - dạo phố buổi tối",
    },
    "ĐÀ NẴNG": {
        "biển": "Biển Mỹ Khê - đi dạo và ngắm bình minh",
        "vẽ": "Bảo tàng Mỹ thuật Đà Nẵng - cho người yêu nghệ thuật",
        "du lịch": "Bán đảo Sơn Trà - đi xe máy ngắm cảnh",
        "_default": "Cầu Rồng & sông Hàn - cà phê ven sông buổi tối",
    },
}


def _offline(city: str, hobbies: str):
    table = _LIB.get(city, _LIB["HÀ NỘI"])
    text = hobbies.lower()
    ideas = []
    for key, sug in table.items():
        if key != "_default" and key in text:
            ideas.append(sug)
    if not ideas:
        ideas.append(table["_default"])
    return ideas[:3]


def suggest_places(a: Dict[str, Any], b: Dict[str, Any],
                   chat_model: str = "gpt-4o-mini",
                   api_key: Optional[str] = None) -> Dict[str, Any]:
    city = a.get("location") or b.get("location") or "HÀ NỘI"
    hobbies = f"{a.get('hobbies', '')}, {b.get('hobbies', '')}"
    provider = get_provider(chat_model, api_key)
    prompt = (f"Cặp đôi: {a.get('name')} & {b.get('name')}, cùng khu vực {city}.\n"
              f"Sở thích: {hobbies}.\nGợi ý 3 địa điểm hẹn hò phù hợp.")
    out = chat(provider, prompt, SYSTEM, chat_model, event="PLACE_SUGGEST")
    if out:
        return {"city": city, "text": out, "source": "llm"}
    ideas = _offline(city, hobbies)
    return {"city": city, "text": "\n".join(f"- {x}" for x in ideas),
            "source": "offline"}
