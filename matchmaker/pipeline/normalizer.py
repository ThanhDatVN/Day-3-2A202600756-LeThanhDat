"""Chuẩn hóa text + khoảng cách địa lý giữa các thành phố."""
from typing import Dict, Any, List

# Alias -> canonical city
_CITY = {
    "hn": "Hà Nội", "ha noi": "Hà Nội", "hà nội": "Hà Nội", "hanoi": "Hà Nội",
    "sg": "TP HCM", "tphcm": "TP HCM", "tp hcm": "TP HCM", "tp.hcm": "TP HCM",
    "sài gòn": "TP HCM", "sai gon": "TP HCM", "hồ chí minh": "TP HCM",
    "đà nẵng": "Đà Nẵng", "da nang": "Đà Nẵng", "đn": "Đà Nẵng",
    "huế": "Huế", "hue": "Huế",
    "cần thơ": "Cần Thơ", "can tho": "Cần Thơ", "ct": "Cần Thơ",
    "hải phòng": "Hải Phòng", "hai phong": "Hải Phòng", "hp": "Hải Phòng",
}

# Khoảng cách xấp xỉ (km) giữa các thành phố. Đối xứng; 0 nếu cùng thành phố.
_DIST = {
    ("Hà Nội", "TP HCM"): 1700, ("Hà Nội", "Đà Nẵng"): 770,
    ("Hà Nội", "Huế"): 660, ("Hà Nội", "Cần Thơ"): 1900, ("Hà Nội", "Hải Phòng"): 120,
    ("TP HCM", "Đà Nẵng"): 850, ("TP HCM", "Huế"): 960, ("TP HCM", "Cần Thơ"): 170,
    ("TP HCM", "Hải Phòng"): 1800,
    ("Đà Nẵng", "Huế"): 100, ("Đà Nẵng", "Cần Thơ"): 1000, ("Đà Nẵng", "Hải Phòng"): 700,
    ("Huế", "Cần Thơ"): 1050, ("Huế", "Hải Phòng"): 600,
    ("Cần Thơ", "Hải Phòng"): 1950,
}


def normalize_location(value: str) -> str:
    key = (value or "").strip().lower()
    return _CITY.get(key, (value or "").strip())


def distance_km(a: str, b: str) -> int:
    a, b = normalize_location(a), normalize_location(b)
    if a == b:
        return 0
    return _DIST.get((a, b)) or _DIST.get((b, a)) or 9999


def normalize_profiles(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lowercase keys, cast types, canonicalize location/gender."""
    out = []
    for r in rows:
        r = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        r["age"] = int(r["age"]) if str(r.get("age", "")).isdigit() else 0
        for f in ("pref_age_min", "pref_age_max", "max_distance_km"):
            r[f] = int(r[f]) if str(r.get(f, "")).isdigit() else 0
        r["gender"] = (r.get("gender", "") or "").lower()
        r["gender_target"] = (r.get("gender_target", "") or "").lower()
        r["wants_children"] = (r.get("wants_children", "") or "").lower()
        r["location"] = normalize_location(r.get("location", ""))
        out.append(r)
    return out
