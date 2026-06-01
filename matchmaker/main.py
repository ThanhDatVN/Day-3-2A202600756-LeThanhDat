"""
Điểm vào: chạy full pipeline mai mối + ReAct Agent cho case khó.

    python -m matchmaker.main

Luồng: đọc Sheet → chuẩn hóa → embedding → Gale-Shapley (case dễ) →
tách case khó → ReAct Agent xử lý từng case → xuất kết quả + email (outbox).
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchmaker import config
from matchmaker.integrations import google_sheets, email_sender
from matchmaker.pipeline.normalizer import normalize_profiles
from matchmaker.pipeline.embedder import Embedder
from matchmaker.pipeline.store import ProfileStore
from matchmaker.pipeline.matcher import gale_shapley
from matchmaker.pipeline.hard_case_detector import detect_hard_cases
from matchmaker.agent.react_agent import ReactAgent

LINE = "═" * 70


def print_trace(state):
    for t in state.trace:
        if t["action"]:
            obs = str(t["observation"])
            if len(obs) > 160:
                obs = obs[:160] + "…"
            th = (t["thought"] or "").strip()
            if th:
                print(f"    💭 {th[:150]}")
            print(f"    ⚙  {t['action']}({_short_args(t['args'])}) → {obs}")
        elif t["thought"]:
            print(f"    💭 {t['thought'][:150]}")


def _short_args(args):
    if not args:
        return ""
    return ", ".join(f"{k}={v}" for k, v in args.items() if k not in ("match_reason",))


def main():
    print(LINE)
    print(" PIPELINE MAI MỐI + ReAct Agent xử lý CASE KHÓ")
    print(LINE)

    raw = google_sheets.read_profiles(config.PROFILES_CSV)
    profiles = normalize_profiles(raw)
    print(f"Đọc {len(profiles)} hồ sơ từ {config.PROFILES_CSV}")

    embedder = Embedder(profiles, api_key=config.OPENAI_API_KEY, model=config.EMBED_MODEL)
    store = ProfileStore(profiles, embedder)
    print(f"Embedding mode: {embedder.mode}")

    gs = gale_shapley(store)
    print(f"\n[Gale-Shapley] Ghép tự động {len(gs['matches'])} cặp cùng thành phố:")
    for m in gs["matches"]:
        a, b = store.get(m["a"]), store.get(m["b"])
        print(f"  {a['name']} ({m['a']}) ↔ {b['name']} ({m['b']})  [{a['location']}]")

    hard = detect_hard_cases(store, gs)
    print(f"\n[Hard-case] {len(hard)} người chưa ghép → đưa cho ReAct Agent: "
          + ", ".join(f"{h}({store.get(h)['name']})" for h in hard))

    agent = ReactAgent(store, model=config.CHAT_MODEL)
    resolved = set(gs["matched_ids"])
    results = []

    for pid in hard:
        if pid in resolved:
            print(f"\n— {pid} đã được giải quyết ở case trước, bỏ qua.")
            continue
        print(f"\n{LINE}\n CASE KHÓ: {pid} ({store.get(pid)['name']}, "
              f"{store.get(pid)['age']}t, {store.get(pid)['location']})\n{LINE}")
        state = agent.run(pid, exclude=resolved)
        print_trace(state)

        r = state.result
        results.append(r)
        if r["type"] == "proposal":
            a, b = store.get(r["profile_id_a"]), store.get(r["profile_id_b"])
            resolved.update((r["profile_id_a"], r["profile_id_b"]))
            print(f"\n  ✅ ĐỀ XUẤT: {a['name']} ({r['profile_id_a']}) ↔ "
                  f"{b['name']} ({r['profile_id_b']}) | confidence {r.get('confidence')}")
            print(f"     Lý do: {r['match_reason'][:160]}")
        else:
            print(f"\n  🚩 FLAG: {store.get(r['profile_id'])['name']} ({r['profile_id']}) — "
                  f"{r['reason']} → {r['suggested_action']}")

    # Xuất kết quả + email cho các đề xuất
    google_sheets.write_results(results, config.RESULTS_PATH)
    proposals = [r for r in results if r["type"] == "proposal"]
    mail = email_sender.send_proposals(store, proposals, config.OUTBOX_DIR)

    print(f"\n{LINE}\n TỔNG KẾT")
    print(LINE)
    print(f"  Ghép tự động (Gale-Shapley): {len(gs['matches'])} cặp")
    print(f"  Case khó xử lý bởi agent   : {len([r for r in results])}")
    print(f"    • Đề xuất (propose_pair) : {len(proposals)}")
    print(f"    • Gắn cờ (flag_unmatched): {len([r for r in results if r['type']=='flag'])}")
    print(f"  Kết quả lưu: {config.RESULTS_PATH}")
    print(f"  Email đề xuất: {mail['mode']}, {mail['count']} thư → {mail['outbox_dir']}")


if __name__ == "__main__":
    main()
