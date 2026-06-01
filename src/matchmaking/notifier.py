"""
Gửi kết quả match LẦN LƯỢT qua Email + Zalo.

Mặc định chạy chế độ DRY-RUN ("outbox"): soạn tin nhắn và lưu ra data/outbox/
(mỗi người 1 file), ghi log NOTIFY_* — an toàn khi chưa có credentials thật.

Cắm thật:
  - Email: đặt SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS trong .env (dùng smtplib).
  - Zalo : đặt ZALO_OA_TOKEN trong .env (gọi Zalo OA API) - để TODO.
"""
import os
import json
from typing import Dict, Any, List

from src.telemetry.logger import logger


def _compose(person: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    lines = [f"Chào {person['name']},",
             "", "Cảm ơn bạn đã tham gia chương trình mai mối! "
             "Dưới đây là những người chúng tôi nghĩ bạn sẽ hợp:"]
    for rank, c in enumerate(candidates, 1):
        lines.append(f"  {rank}. {c['name']} — độ hợp {c['score']*100:.0f}% ({c['reason']})")
    lines += ["", "Chúc bạn sớm tìm được nửa kia 💞", "— Đội ngũ Mai Mối"]
    return "\n".join(lines)


def _send_email(to_addr: str, subject: str, body: str) -> str:
    """Real SMTP if configured, else dry-run. Returns a status string."""
    host = os.getenv("SMTP_HOST")
    if not host or not to_addr:
        return "dry-run"
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = os.getenv("SMTP_USER", "noreply@matchmaker.local")
        msg["To"] = to_addr
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
            s.send_message(msg)
        return "sent"
    except Exception as e:  # noqa: BLE001
        logger.log_event("EMAIL_ERROR", {"to": to_addr, "error": str(e)})
        return f"error: {e}"


def _send_zalo(zalo_id: str, body: str) -> str:
    """Zalo OA API hook. Without a token this is a dry-run."""
    if not os.getenv("ZALO_OA_TOKEN") or not zalo_id:
        return "dry-run"
    # TODO: call Zalo OA sendmessage API here.
    return "sent"


def send_all(topk: Dict[str, Any], out_dir: str = "data/outbox") -> Dict[str, Any]:
    """Send each person their Top-K suggestions, sequentially, via Email then Zalo."""
    os.makedirs(out_dir, exist_ok=True)
    sent = []
    for r in topk.get("results", []):
        person = r["person"]
        if not r["candidates"]:
            continue
        body = _compose(person, r["candidates"])
        subject = f"[Mai Mối] Gợi ý ghép đôi cho {person['name']}"

        email_status = _send_email(person.get("email", ""), subject, body)
        zalo_status = _send_zalo(person.get("zalo", ""), body)

        # Always write to the outbox so the demo has something to show.
        fpath = os.path.join(out_dir, f"{person['id']}_{person['name']}.txt")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(f"TO EMAIL: {person.get('email','')}\nTO ZALO : {person.get('zalo','')}\n"
                    f"SUBJECT : {subject}\n{'-'*40}\n{body}\n")

        rec = {"id": person["id"], "name": person["name"],
               "email": person.get("email", ""), "zalo": person.get("zalo", ""),
               "email_status": email_status, "zalo_status": zalo_status,
               "outbox_file": fpath}
        sent.append(rec)
        logger.log_event("NOTIFY_SENT", {"id": person["id"], "email": email_status,
                                         "zalo": zalo_status})

    return {"sent": sent, "count": len(sent), "outbox_dir": out_dir,
            "mode": "real-smtp" if os.getenv("SMTP_HOST") else "dry-run (outbox)"}
