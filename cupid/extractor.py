"""
Trích xuất thông tin có cấu trúc từ MÔ TẢ NGÔN NGỮ TỰ NHIÊN của người dùng.

Gọi OpenAI (JSON mode) để map mô tả tự do → đúng các trường của dataset.
"""
from typing import Dict, Any

from cupid import llm

SYSTEM = """Bạn là bộ trích xuất hồ sơ hẹn hò. Người dùng mô tả bản thân bằng ngôn ngữ tự nhiên.
Hãy trích xuất CHÍNH XÁC thành JSON với đúng các khóa sau (không thêm khóa khác):
{
  "name": string,            // tên, nếu không rõ để ""
  "age": number,             // tuổi, nếu không rõ để 0
  "gender": "Nam" | "Nữ",   // suy ra; nếu không rõ để ""
  "address": string,         // tỉnh/thành, nếu không rõ để ""
  "hobbies": string,         // sở thích, gộp thành 1 chuỗi phân tách bằng dấu phẩy
  "requirements": string     // yêu cầu/mong muốn ở đối phương
}
Chỉ trả JSON, không giải thích."""


def extract(nl_text: str) -> Dict[str, Any]:
    data = llm.chat_json(SYSTEM, nl_text)
    # Chuẩn hóa & đảm bảo đủ khóa
    profile = {
        "name": str(data.get("name", "") or "").strip() or "Bạn",
        "age": int(data["age"]) if str(data.get("age", "")).strip().isdigit() else 0,
        "gender": _norm_gender(data.get("gender", "")),
        "address": str(data.get("address", "") or "").strip(),
        "hobbies": str(data.get("hobbies", "") or "").strip(),
        "requirements": str(data.get("requirements", "") or "").strip(),
    }
    llm.log("EXTRACT", {"input": nl_text[:200], "profile": profile})
    return profile


def _norm_gender(g: str) -> str:
    g = (g or "").strip().lower()
    if g in ("nam", "male", "m", "trai", "boy"):
        return "Nam"
    if g in ("nữ", "nu", "female", "f", "gái", "girl"):
        return "Nữ"
    return ""
