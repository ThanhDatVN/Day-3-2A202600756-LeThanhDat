"""
Terminal demo cho Agent Mai Mối (không cần trình duyệt).

Cách dùng:
    # Chế độ tương tác (chat trong terminal):
    python demo.py

    # Hỏi nhanh một câu rồi thoát:
    python demo.py "Tìm người hợp nhất với P01"

    # Ghép cặp toàn bộ sheet rồi thoát:
    python demo.py --match-all
"""
import os
import sys

# Bảo đảm in được tiếng Việt trên console Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.matchmaking.matcher import Matchmaker
from src.matchmaking.agent import MatchmakingAgent

LINE = "─" * 64


def print_profiles(mm):
    print(LINE)
    print(f"📋 DANH SÁCH HỒ SƠ (similarity mode: {mm.mode})")
    print(LINE)
    for p in mm.profiles:
        print(f"  {p['ID']}  {p['NAME']:<6} {p['GENDER']:<3} {p['AGE']}t  {p['LOCATION']:<8}"
              f" | ❤ {p['HOBBIES']}")


def print_match_all(mm):
    res = mm.match_all()
    paths = mm.export(res)
    print(LINE)
    print(f"💞 GHÉP CẶP TOÀN BỘ — {res['stats']['matched_pairs']} cặp / "
          f"{res['stats']['total_profiles']} hồ sơ")
    print(LINE)
    for pr in res["pairs"]:
        print(f"  {pr['a']['name']:<6} 💕 {pr['b']['name']:<6}  {pr['score']*100:4.0f}%"
              f"  | {pr['reason']}")
    if res["unmatched"]:
        print("  Chưa ghép:", ", ".join(u["name"] for u in res["unmatched"]))
    print(f"\n  → Đã xuất: {paths['csv']} , {paths['json']}")


def print_answer(agent, query):
    print(LINE)
    print(f"🤖 AGENT trả lời: \"{query}\"")
    print(LINE)
    out = agent.answer(query)
    print(out["answer"])
    data = out.get("data", {})
    if data.get("candidates"):
        print("\n  Ứng viên (xếp hạng):")
        for c in data["candidates"]:
            print(f"   - {c['id']} {c['name']:<6} {c['score']*100:4.0f}%  | {c['reason']}")


def main():
    mm = Matchmaker(csv_path=os.getenv("PROFILES_CSV", "data/profiles.csv"))
    agent = MatchmakingAgent(mm, chat_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    args = sys.argv[1:]

    # Một lệnh rồi thoát.
    if args:
        if args[0] in ("--match-all", "-a"):
            print_profiles(mm)
            print_match_all(mm)
        else:
            print_answer(agent, " ".join(args))
        return

    # Chế độ tương tác.
    print_profiles(mm)
    print_match_all(mm)
    print(LINE)
    print("💬 Chế độ chat — gõ câu hỏi (vd: 'Tìm người hợp với P05').")
    print("   Lệnh: 'all' = ghép tất cả | 'list' = xem hồ sơ | 'thoat' = thoát")
    print(LINE)
    while True:
        try:
            q = input("\nBạn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt! 👋")
            break
        if not q:
            continue
        if q.lower() in ("thoat", "exit", "quit", "q"):
            print("Tạm biệt! 👋")
            break
        if q.lower() == "list":
            print_profiles(mm)
            continue
        if q.lower() == "all":
            print_match_all(mm)
            continue
        print_answer(agent, q)


if __name__ == "__main__":
    main()
