"""
ProfileStore: lớp truy cập dữ liệu cho agent.

Đây là nơi GIỮ TOÀN BỘ DỮ LIỆU NHẠY CẢM. Agent/LLM không bao giờ nhận cả sheet;
nó chỉ thao tác qua các method ở đây bằng PROFILE_ID. Mọi method đều kiểm tra ID
tồn tại (ID-guard) để LLM không thể bịa/đổi nhầm id người.

`anon()` tạo "view ẩn danh" (bỏ name/email/phone) — đó là thứ duy nhất được đẩy
sang LLM.
"""
from typing import Dict, Any, List, Optional, Set

from matchmaker.pipeline.embedder import Embedder
from matchmaker.pipeline.normalizer import normalize_location, distance_km


class ProfileStore:
    def __init__(self, profiles: List[Dict[str, Any]], embedder: Embedder):
        self.profiles: Dict[str, Dict[str, Any]] = {p["id"]: p for p in profiles}
        self.embedder = embedder

    # ----- ID safety -----
    def exists(self, pid: str) -> bool:
        return pid in self.profiles

    def get(self, pid: str) -> Optional[Dict[str, Any]]:
        return self.profiles.get(pid)

    def anon(self, pid: str) -> Dict[str, Any]:
        """View ẩn danh đẩy cho LLM: chỉ đặc điểm, KHÔNG tên/email/SĐT."""
        p = self.profiles[pid]
        return {
            "id": p["id"], "age": p["age"], "gender": p["gender"],
            "gender_target": p["gender_target"], "location": p["location"],
            "interests": p["interests"], "values": p["values"],
            "lifestyle": p["lifestyle"], "wants_children": p["wants_children"],
            "pref_age_min": p["pref_age_min"], "pref_age_max": p["pref_age_max"],
        }

    # ----- queries used by tools -----
    def query(self, gender_target: str, age_min: int, age_max: int,
              location: str = "any", top_k: int = 5,
              exclude: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        exclude = exclude or set()
        loc = None if (location or "").lower() in ("any", "", "bất kỳ") else normalize_location(location)
        res = []
        for pid, p in self.profiles.items():
            if pid in exclude:
                continue
            if p["gender"] != gender_target:
                continue
            if not (age_min <= p["age"] <= age_max):
                continue
            if loc and p["location"] != loc:
                continue
            res.append(self.anon(pid))
        return res[:top_k]

    def similarity(self, id_a: str, id_b: str) -> Dict[str, Any]:
        return self.embedder.similarity(id_a, id_b)

    def check_hard_constraints(self, id_a: str, id_b: str) -> Dict[str, Any]:
        a, b = self.profiles[id_a], self.profiles[id_b]
        violations = []
        if not (a["pref_age_min"] <= b["age"] <= a["pref_age_max"]):
            violations.append(f"{id_b} ({b['age']}t) ngoài khoảng tuổi {id_a} mong muốn")
        if not (b["pref_age_min"] <= a["age"] <= b["pref_age_max"]):
            violations.append(f"{id_a} ({a['age']}t) ngoài khoảng tuổi {id_b} mong muốn")
        if {a["wants_children"], b["wants_children"]} == {"yes", "no"}:
            violations.append("quan điểm con cái trái ngược (một bên muốn, một bên không)")
        d = distance_km(a["location"], b["location"])
        if d > min(a["max_distance_km"], b["max_distance_km"]):
            violations.append(f"khoảng cách {d}km vượt giới hạn cho phép")
        return {"passed": not violations, "violations": violations, "distance_km": d}
