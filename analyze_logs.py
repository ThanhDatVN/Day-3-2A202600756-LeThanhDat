"""
Log analyzer / metrics dashboard for Lab 3.

Parses the structured JSON events in logs/ and computes the industry metrics
from EVALUATION.md:
  * Token efficiency (prompt vs completion, total)
  * Latency (p50 / p95 / max)
  * Cost
  * Loop count per agent run (steps)
  * Failure analysis (JSON parse errors, hallucinations, timeouts)
  * Aggregate reliability of Agent v1 vs v2

Usage:
    python analyze_logs.py                # newest log file
    python analyze_logs.py logs/2026-06-01.log
"""
import os
import sys
import glob
import json
from collections import Counter, defaultdict


def load_events(path):
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip non-JSON console noise
    return events


def percentile(values, p):
    if not values:
        return 0
    s = sorted(values)
    k = int(round((p / 100) * (len(s) - 1)))
    return s[k]


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join("logs", "*.log")))
        if not files:
            print("No log files found in logs/. Run `python main.py` first.")
            return
        path = files[-1]

    events = load_events(path)
    if not events:
        print(f"No JSON events parsed from {path}.")
        return

    print("=" * 70)
    print(f" METRICS DASHBOARD  -  {path}  ({len(events)} events)")
    print("=" * 70)

    # ---- Token & latency & cost (from LLM_METRIC events) ----
    metrics = [e["data"] for e in events if e.get("event") == "LLM_METRIC"]
    if metrics:
        prompt_toks = [m["prompt_tokens"] for m in metrics]
        compl_toks = [m["completion_tokens"] for m in metrics]
        total_toks = [m["total_tokens"] for m in metrics]
        latencies = [m["latency_ms"] for m in metrics]
        costs = [m.get("cost_estimate", 0) for m in metrics]

        print("\n[1] TOKEN EFFICIENCY")
        print(f"    LLM calls          : {len(metrics)}")
        print(f"    Prompt tokens      : total {sum(prompt_toks)}, avg {sum(prompt_toks)//len(metrics)}")
        print(f"    Completion tokens  : total {sum(compl_toks)}, avg {sum(compl_toks)//len(metrics)}")
        print(f"    Total tokens       : {sum(total_toks)}")
        ratio = (sum(compl_toks) / sum(prompt_toks)) if sum(prompt_toks) else 0
        print(f"    Completion/Prompt  : {ratio:.2f}")

        print("\n[2] LATENCY (ms)")
        print(f"    p50 {percentile(latencies,50)} | p95 {percentile(latencies,95)} | "
              f"max {max(latencies)} | avg {sum(latencies)//len(latencies)}")

        print("\n[3] COST")
        print(f"    Estimated total    : ${sum(costs):.6f}")
        by_model = defaultdict(float)
        for m in metrics:
            by_model[m["model"]] += m.get("cost_estimate", 0)
        for model, c in by_model.items():
            print(f"      {model:24} ${c:.6f}")
    else:
        print("\nNo LLM_METRIC events found.")

    # ---- Loop count per agent run ----
    print("\n[4] LOOP COUNT (steps per agent run)")
    ends = [e["data"] for e in events if e.get("event") == "AGENT_END"]
    if ends:
        steps = [e.get("steps", 0) for e in ends]
        by_version = defaultdict(list)
        for e in ends:
            by_version[e.get("version", "?")].append(e.get("steps", 0))
        print(f"    Agent runs         : {len(ends)}")
        print(f"    Avg steps          : {sum(steps)/len(steps):.2f} | max {max(steps)}")
        for v, s in by_version.items():
            print(f"      {v}: avg {sum(s)/len(s):.2f} steps over {len(s)} runs")
    else:
        print("    No AGENT_END events.")

    # ---- Failure analysis ----
    print("\n[5] FAILURE ANALYSIS (error event counts)")
    failure_events = ["JSON_PARSE_ERROR", "PARSE_ERROR", "HALLUCINATION_ERROR",
                      "TOOL_ARG_ERROR", "TOOL_RUNTIME_ERROR", "TIMEOUT"]
    counts = Counter(e["event"] for e in events if e.get("event") in failure_events)
    if counts:
        for ev in failure_events:
            if counts.get(ev):
                print(f"    {ev:22}: {counts[ev]}")
    else:
        print("    No failures recorded. 🎉")

    # ---- Aggregate reliability v1 vs v2 ----
    print("\n[6] AGGREGATE RELIABILITY (agent success by version)")
    succ = defaultdict(lambda: [0, 0])  # version -> [success, total]
    for e in ends:
        v = e.get("version", "?")
        succ[v][1] += 1
        if e.get("success"):
            succ[v][0] += 1
    for v, (s, t) in sorted(succ.items()):
        rate = (100 * s // t) if t else 0
        print(f"    {v}: {s}/{t} successful runs ({rate}%)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
