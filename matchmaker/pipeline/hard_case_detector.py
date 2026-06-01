"""
Tách nhóm "case khó" sau bước Gale-Shapley.

Case khó = người chưa được ghép bởi thuật toán chính (không có ứng viên cùng
thành phố phù hợp). Sắp xếp để xử lý ổn định (nam trước, rồi nữ; theo id).
"""
from typing import Dict, Any, List

from matchmaker.pipeline.store import ProfileStore


def detect_hard_cases(store: ProfileStore, gs_result: Dict[str, Any]) -> List[str]:
    unmatched = gs_result["unmatched"]
    males = sorted(u for u in unmatched if store.get(u)["gender"] == "male")
    females = sorted(u for u in unmatched if store.get(u)["gender"] == "female")
    return males + females
