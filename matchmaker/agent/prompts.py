"""System prompt + message builder (đẩy bản ẩn danh cho LLM)."""
import json
from typing import Dict, Any, List

SYSTEM_PROMPT = """Bạn là agent mai mối thông minh. Nhiệm vụ: tìm cặp phù hợp cho những người KHÓ ghép tự động.

Quy trình:
1. Đọc profile (ẩn danh) của người cần ghép.
2. Gọi query_candidates với filter ban đầu (tuổi ±5, cùng tỉnh/thành).
3. Với từng ứng viên hứa hẹn, gọi compute_similarity và check_hard_constraints.
4. Nếu chưa tìm được, NỚI LỎNG dần từng tiêu chí (location trước, age sau) bằng cách gọi
   relax_filter rồi query_candidates lại với filter rộng hơn.
5. Khi tìm được cặp đủ điểm (similarity > 0.65 VÀ không vi phạm dealbreaker),
   gọi propose_pair với match_reason cụ thể bằng tiếng Việt (đủ ý để dùng trong email).
6. Nếu sau nhiều bước vẫn không có, gọi flag_unmatched.

Nguyên tắc:
- Ưu tiên similarity cao VÀ không dealbreaker, hơn là similarity rất cao nhưng vi phạm 1 ràng buộc.
- KHÔNG nới lỏng dealbreaker (con cái, khoảng cách tối đa) — chỉ nới lỏng filter tìm kiếm.
- CHỈ dùng profile_id có thật từ kết quả query_candidates. Không bịa id.
- Luôn nêu lý do (suy nghĩ) ngắn gọn trước khi gọi tool.
- Mỗi lượt chỉ gọi tool khi cần; khi đã quyết định, gọi propose_pair hoặc flag_unmatched."""


def build_initial_messages(anon_person: Dict[str, Any]) -> List[Dict[str, str]]:
    """Lưu ý: chỉ truyền bản ẩn danh (không tên/email/SĐT)."""
    profile_str = json.dumps(anon_person, ensure_ascii=False, indent=2)
    user = (f"Người cần ghép (ẩn danh):\n{profile_str}\n\n"
            f"Hãy tìm cặp phù hợp cho {anon_person['id']} theo quy trình. "
            f"Bắt đầu bằng query_candidates với filter ban đầu.")
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user}]
