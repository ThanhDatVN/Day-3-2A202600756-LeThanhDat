"""
Tạo "Match Report" — báo cáo kết quả ghép đôi (Markdown), lưu ra report/.
"""
import os
from typing import Dict, Any, Optional


def build_report(topk: Dict[str, Any], greedy: Dict[str, Any],
                 review: Optional[Dict[str, Any]] = None,
                 out_path: str = "report/MATCH_REPORT.md") -> Dict[str, Any]:
    w = topk.get("weights", {})
    stats = topk.get("stats", {})
    lines = [
        "# Match Report — Agent Mai Mối",
        "",
        f"- Tổng hồ sơ: **{stats.get('total_profiles', '?')}**",
        f"- Top-K mỗi người: **{stats.get('k', '?')}**",
        f"- Chế độ tương đồng: **{stats.get('similarity_mode', '?')}**",
        f"- Trọng số tầng: semantic {w.get('semantic')}, hobbies {w.get('hobbies')}, "
        f"location {w.get('location')}, age {w.get('age')}",
        "",
    ]

    if review:
        lines += [
            "## 1. AI Review dữ liệu",
            f"- Sẵn sàng match: **{'CÓ' if review['ready_to_match'] else 'CHƯA'}** "
            f"({review['errors']} lỗi, {review['warnings']} cảnh báo)",
            f"- Nhận xét AI: {review['ai_note']}",
            "",
        ]
        if review["issues"]:
            lines.append("| Hồ sơ | Mức | Vấn đề |")
            lines.append("| :--- | :--- | :--- |")
            for it in review["issues"][:20]:
                lines.append(f"| {it['id']} | {it['severity']} | {it['message']} |")
            lines.append("")

    lines += ["## 2. Tổng quan ghép cặp 1-1 (tham khảo)",
              f"- Ghép {greedy['stats']['matched_pairs']} cặp / "
              f"{greedy['stats']['total_profiles']} hồ sơ, "
              f"{greedy['stats']['unmatched']} chưa ghép.", ""]
    lines.append("| A | B | Điểm | Lý do |")
    lines.append("| :--- | :--- | :--- | :--- |")
    for pr in greedy["pairs"]:
        lines.append(f"| {pr['a']['name']} ({pr['a']['id']}) | {pr['b']['name']} "
                     f"({pr['b']['id']}) | {pr['score']*100:.0f}% | {pr['reason']} |")
    lines.append("")

    lines.append("## 3. Top-K gợi ý cho từng người")
    for r in topk["results"]:
        p = r["person"]
        tops = "; ".join(f"{c['name']} ({c['score']*100:.0f}%)" for c in r["candidates"])
        lines.append(f"- **{p['name']} ({p['id']}, {p['gender']}, {p['age']}, {p['location']})** → {tops}")
    lines.append("")

    markdown = "\n".join(lines)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return {"path": out_path, "markdown": markdown}
