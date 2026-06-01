"""
Gửi email kết quả ĐỀ XUẤT (chờ admin xác nhận).

Quan trọng: tên/email thật chỉ được tra ở ĐÂY (sau khi agent đã quyết định bằng
ID) — LLM không bao giờ thấy chúng. Mặc định dry-run: lưu ra outbox.
"""
import os
from typing import List, Dict, Any

from matchmaker.pipeline.store import ProfileStore


def _compose(store: ProfileStore, prop: Dict[str, Any]) -> Dict[str, str]:
    a = store.get(prop["profile_id_a"])
    b = store.get(prop["profile_id_b"])
    body = (f"Chào {a['name']},\n\n"
            f"Hệ thống mai mối có một gợi ý dành cho bạn: {b['name']} "
            f"({b['age']} tuổi, {b['location']}).\n\n"
            f"Lý do phù hợp: {prop['match_reason']}\n\n"
            f"(Độ tin cậy: {prop.get('confidence')}. Đây là ĐỀ XUẤT — đội ngũ sẽ "
            f"xác nhận trước khi kết nối hai bạn.)\n\n— Đội ngũ Mai Mối")
    return {"to": a["email"], "to_name": a["name"], "subject":
            f"[Mai Mối] Gợi ý kết nối cho {a['name']}", "body": body}


def send_proposals(store: ProfileStore, proposals: List[Dict[str, Any]],
                   outbox_dir: str) -> Dict[str, Any]:
    os.makedirs(outbox_dir, exist_ok=True)
    sent = []
    for prop in proposals:
        mail = _compose(store, prop)
        fpath = os.path.join(outbox_dir, f"{prop['profile_id_a']}_to_{prop['profile_id_b']}.txt")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"TO: {mail['to']}\nSUBJECT: {mail['subject']}\n{'-'*40}\n{mail['body']}\n")
        sent.append({"to": mail["to"], "subject": mail["subject"], "file": fpath,
                     "status": "real-smtp" if os.getenv("SMTP_HOST") else "dry-run"})
    return {"count": len(sent), "outbox_dir": outbox_dir, "sent": sent,
            "mode": "real-smtp" if os.getenv("SMTP_HOST") else "dry-run (outbox)"}
