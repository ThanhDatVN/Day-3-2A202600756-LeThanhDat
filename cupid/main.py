"""
Demo terminal cho Cupid.

    python -m cupid.main "Mình là Hùng, 29 tuổi, nam, ở Hà Nội, thích trekking…"
    python -m cupid.main          # nhập tương tác
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from cupid import agent

LINE = "─" * 64


def show(res):
    p = res["profile"]
    print(LINE)
    print(f"HỒ SƠ (AI trích xuất): {p['name']}, {p['age']}t, {p['gender']}, {p['address']}")
    print(f"  ❤ {p['hobbies']}  | 🔎 {p['requirements']}")
    if res["waitlist_hits"]:
        print("🎉 Người đang chờ phù hợp với bạn: "
              + ", ".join(f"{h['waiter']['name']} ({h['score']*100:.0f}%)" for h in res["waitlist_hits"]))
    print(LINE)
    print("TOP 5 GỢI Ý:")
    for i, c in enumerate(res["candidates"], 1):
        print(f"{i}. {c['name']} ({c['gender']}, {c['age']}, {c['address']})  "
              f"{c['score']*100:.0f}%  [{c.get('label','')}]")
        print(f"   📝 {c.get('assessment','')}")
        print(f"   💡 {c.get('advice','')}")


def main():
    args = sys.argv[1:]
    if args:
        show(agent.process(" ".join(args)))
        return
    print("Nhập mô tả bản thân (gõ 'thoat' để thoát):")
    while True:
        try:
            nl = input("\nBạn> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if nl.lower() in ("thoat", "exit", "quit"):
            break
        if nl:
            show(agent.process(nl))


if __name__ == "__main__":
    main()
