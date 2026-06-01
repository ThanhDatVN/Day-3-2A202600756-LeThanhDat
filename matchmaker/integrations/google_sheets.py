"""
Đọc/ghi "Google Sheet". Bản demo đọc CSV cục bộ mô phỏng Sheet.

Cắm Sheet thật: đặt SHEET_ID trong .env và dùng gspread + service account
(thay thân hàm read_profiles). Giữ nguyên chữ ký hàm để phần còn lại không đổi.
"""
import os
import csv
import json
from typing import List, Dict, Any


def read_profiles(csv_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Không thấy sheet: {csv_path}")
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_results(results: List[Dict[str, Any]], path: str) -> str:
    """Ghi kết quả (proposal/flag) ra JSON — mô phỏng 'xuất sang sheet mới'."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return path
