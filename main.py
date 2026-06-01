"""
Lab 3 runner: Chatbot vs ReAct Agent.

Usage:
    python main.py                       # full comparison on all test cases (mock)
    python main.py --provider openai     # use a real provider
    python main.py --mode agent --version v2 "your question here"
    python main.py --mode chatbot "your question here"

Everything is logged to logs/YYYY-MM-DD.log; run `python analyze_logs.py` after.
"""
import os
import sys
import argparse

from dotenv import load_dotenv

# Make `src` importable when run from the project root.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.factory import create_provider
from src.agent.agent import ReActAgent
from src.agent.chatbot import Chatbot
from src.tools import get_all_tools
from src.eval.test_cases import TEST_CASES, is_correct


def _max_steps() -> int:
    try:
        return int(os.getenv("AGENT_MAX_STEPS", "6"))
    except ValueError:
        return 6


def run_single(provider_name, mode, version, question):
    llm = create_provider(provider_name)
    if mode == "chatbot":
        bot = Chatbot(llm)
        print(f"\n[Chatbot | {llm.model_name}]")
        print("Answer:", bot.run(question))
    else:
        agent = ReActAgent(llm, get_all_tools(), max_steps=_max_steps(), version=version)
        print(f"\n[Agent {version} | {llm.model_name}]")
        print("Answer:", agent.run(question))


def run_comparison(provider_name):
    print("=" * 78)
    print(f" CHATBOT vs ReAct AGENT  -  provider={provider_name or os.getenv('DEFAULT_PROVIDER', 'mock')}")
    print("=" * 78)

    rows = []
    for case in TEST_CASES:
        q = case["prompt"]
        # Fresh provider per run so nothing leaks between calls.
        chatbot_ans = Chatbot(create_provider(provider_name)).run(q)
        agent_v1 = ReActAgent(create_provider(provider_name), get_all_tools(),
                              max_steps=_max_steps(), version="v1").run(q)
        agent_v2 = ReActAgent(create_provider(provider_name), get_all_tools(),
                              max_steps=_max_steps(), version="v2").run(q)

        rows.append({
            "id": case["id"],
            "kind": case["kind"],
            "chatbot": is_correct(chatbot_ans, case),
            "v1": is_correct(agent_v1, case),
            "v2": is_correct(agent_v2, case),
        })

        print(f"\n--- {case['id']} ({case['kind']}): {q}")
        print(f"   Chatbot : {'PASS' if rows[-1]['chatbot'] else 'FAIL'}  | {chatbot_ans[:90]}")
        print(f"   Agent v1: {'PASS' if rows[-1]['v1'] else 'FAIL'}  | {agent_v1[:90]}")
        print(f"   Agent v2: {'PASS' if rows[-1]['v2'] else 'FAIL'}  | {agent_v2[:90]}")

    # Summary table
    print("\n" + "=" * 78)
    print(f"{'Case':6}{'Kind':8}{'Chatbot':10}{'Agent v1':10}{'Agent v2':10}")
    print("-" * 78)
    for r in rows:
        print(f"{r['id']:6}{r['kind']:8}"
              f"{('PASS' if r['chatbot'] else 'FAIL'):10}"
              f"{('PASS' if r['v1'] else 'FAIL'):10}"
              f"{('PASS' if r['v2'] else 'FAIL'):10}")
    print("-" * 78)
    n = len(rows)
    for col in ("chatbot", "v1", "v2"):
        passed = sum(1 for r in rows if r[col])
        print(f"{col:>10}: {passed}/{n} passed ({100*passed//n}%)")
    print("=" * 78)
    print("\nLogs written to logs/. Run `python analyze_logs.py` for the metrics dashboard.")


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Lab 3: Chatbot vs ReAct Agent")
    parser.add_argument("question", nargs="?", help="Single question to ask")
    parser.add_argument("--provider", default=None, help="mock|openai|gemini|local")
    parser.add_argument("--mode", default="compare", choices=["compare", "agent", "chatbot"])
    parser.add_argument("--version", default="v2", choices=["v1", "v2"])
    args = parser.parse_args()

    if args.mode == "compare" and not args.question:
        run_comparison(args.provider)
    else:
        if not args.question:
            print("Please provide a question, e.g.: python main.py --mode agent \"...\"")
            sys.exit(1)
        run_single(args.provider, args.mode, args.version, args.question)


if __name__ == "__main__":
    main()
