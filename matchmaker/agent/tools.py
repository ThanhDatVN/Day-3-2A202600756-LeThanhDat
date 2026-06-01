"""
Định nghĩa + thực thi 6 tools cho OpenAI function calling.

Triết lý (theo yêu cầu): KHÔNG đưa cả sheet cho LLM để nó tự ghép. LLM chỉ gọi
tool bằng PROFILE_ID; mọi tính toán (similarity, ràng buộc, truy vấn) chạy
DETERMINISTIC ở đây. Mỗi tool có ID-GUARD: nếu id không tồn tại → trả lỗi, nên
LLM không thể bịa hay đổi nhầm id người.
"""
import json
from typing import Dict, Any, List, Optional, Set

from matchmaker.pipeline.store import ProfileStore

# ---- JSON schema cho function calling ----
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "query_candidates",
        "description": "Tìm ứng viên phù hợp theo bộ lọc. Trả về danh sách profile ẩn danh (chỉ id + đặc điểm).",
        "parameters": {"type": "object", "properties": {
            "gender_target": {"type": "string", "enum": ["male", "female"]},
            "age_min": {"type": "integer"},
            "age_max": {"type": "integer"},
            "location": {"type": "string", "description": "tỉnh/thành, hoặc 'any' để bỏ qua"},
            "top_k": {"type": "integer", "description": "số kết quả tối đa, mặc định 5"},
        }, "required": ["gender_target", "age_min", "age_max"]},
    }},
    {"type": "function", "function": {
        "name": "compute_similarity",
        "description": "Tính cosine similarity (0-1) giữa hai profile theo sở thích/giá trị/lối sống.",
        "parameters": {"type": "object", "properties": {
            "profile_id_a": {"type": "string"},
            "profile_id_b": {"type": "string"},
        }, "required": ["profile_id_a", "profile_id_b"]},
    }},
    {"type": "function", "function": {
        "name": "check_hard_constraints",
        "description": "Kiểm tra dealbreaker: khoảng tuổi mong muốn, quan điểm con cái, khoảng cách địa lý.",
        "parameters": {"type": "object", "properties": {
            "profile_id_a": {"type": "string"},
            "profile_id_b": {"type": "string"},
        }, "required": ["profile_id_a", "profile_id_b"]},
    }},
    {"type": "function", "function": {
        "name": "relax_filter",
        "description": "Ghi nhận việc nới lỏng một tiêu chí TÌM KIẾM (không phải dealbreaker) để query rộng hơn.",
        "parameters": {"type": "object", "properties": {
            "field": {"type": "string", "enum": ["location", "age_range", "interests"]},
            "from_value": {"type": "string"},
            "to_value": {"type": "string"},
            "reason": {"type": "string"},
        }, "required": ["field", "from_value", "to_value", "reason"]},
    }},
    {"type": "function", "function": {
        "name": "propose_pair",
        "description": "Đề xuất ghép hai người khi đã đủ căn cứ (similarity cao, không vi phạm dealbreaker).",
        "parameters": {"type": "object", "properties": {
            "profile_id_a": {"type": "string"},
            "profile_id_b": {"type": "string"},
            "match_reason": {"type": "string", "description": "lý do hợp, đủ ý để dùng trong email"},
            "confidence": {"type": "number"},
            "admin_note": {"type": "string"},
        }, "required": ["profile_id_a", "profile_id_b", "match_reason", "confidence"]},
    }},
    {"type": "function", "function": {
        "name": "flag_unmatched",
        "description": "Khi đã thử hết phương án mà không tìm được cặp phù hợp.",
        "parameters": {"type": "object", "properties": {
            "profile_id": {"type": "string"},
            "reason": {"type": "string"},
            "suggested_action": {"type": "string"},
        }, "required": ["profile_id", "reason", "suggested_action"]},
    }},
]

# Tool kết thúc vòng lặp (ra quyết định cuối)
TERMINAL_TOOLS = {"propose_pair", "flag_unmatched"}


class ToolExecutor:
    def __init__(self, store: ProfileStore, person_id: str,
                 exclude: Optional[Set[str]] = None):
        self.store = store
        self.person_id = person_id
        self.exclude = set(exclude or set()) | {person_id}
        self.result: Optional[Dict[str, Any]] = None
        self.relaxations: List[Dict[str, Any]] = []

    def _guard(self, *ids) -> Optional[Dict[str, Any]]:
        for pid in ids:
            if not self.store.exists(pid):
                return {"error": f"ID '{pid}' không tồn tại. Chỉ dùng id có trong kết quả query_candidates."}
        return None

    def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return getattr(self, f"_t_{name}")(args)
        except AttributeError:
            return {"error": f"Tool '{name}' không tồn tại."}
        except Exception as e:  # noqa: BLE001
            return {"error": f"Lỗi khi chạy '{name}': {e}"}

    # ---- tool implementations ----
    def _t_query_candidates(self, a):
        cands = self.store.query(
            gender_target=a["gender_target"], age_min=a["age_min"], age_max=a["age_max"],
            location=a.get("location", "any"), top_k=int(a.get("top_k", 5)),
            exclude=self.exclude)
        return {"count": len(cands), "candidates": cands}

    def _t_compute_similarity(self, a):
        err = self._guard(a["profile_id_a"], a["profile_id_b"])
        if err:
            return err
        return self.store.similarity(a["profile_id_a"], a["profile_id_b"])

    def _t_check_hard_constraints(self, a):
        err = self._guard(a["profile_id_a"], a["profile_id_b"])
        if err:
            return err
        return self.store.check_hard_constraints(a["profile_id_a"], a["profile_id_b"])

    def _t_relax_filter(self, a):
        rec = {"field": a["field"], "from": a["from_value"], "to": a["to_value"],
               "reason": a["reason"]}
        self.relaxations.append(rec)
        return {"ok": True, "note": f"Đã nới lỏng {a['field']}: {a['from_value']} → {a['to_value']}"}

    def _t_propose_pair(self, a):
        err = self._guard(a["profile_id_a"], a["profile_id_b"])
        if err:
            return err
        self.result = {
            "type": "proposal", "profile_id_a": a["profile_id_a"], "profile_id_b": a["profile_id_b"],
            "match_reason": a["match_reason"], "confidence": a.get("confidence"),
            "admin_note": a.get("admin_note", ""), "relaxations": list(self.relaxations),
        }
        return {"ok": True, "saved": "proposal (chờ admin xác nhận)"}

    def _t_flag_unmatched(self, a):
        err = self._guard(a["profile_id"])
        if err:
            return err
        self.result = {
            "type": "flag", "profile_id": a["profile_id"], "reason": a["reason"],
            "suggested_action": a["suggested_action"], "relaxations": list(self.relaxations),
        }
        return {"ok": True, "saved": "flagged unmatched"}
