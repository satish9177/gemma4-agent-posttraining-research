"""Pre-freeze structure probe for the compaction-thinking analysis.

Reads only structural fields: arm, task, times, has_tools, errors, finish_reason, n_messages, hist_assistant and the
compaction log. It never reads or prints reasoning_chars, reasoning_text, hist_with_reasoning, hist_reasoning_chars or
anything derived from them, so it cannot reveal the outcome. Its output is kept as probe_stdout.txt.
Usage: python -I -B -X utf8 probe_structure.py
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SETS = {"E7": "audit/e7/e7_output", "E8": "audit/e8/e8_output", "E9": "audit/e9_runtime_pilot/e9_output"}
STRUCT = ("arm", "task", "t0", "t1", "has_tools", "call_error", "ledger_error", "finish_reason", "n_messages",
          "hist_assistant")


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    for name, d in SETS.items():
        led = [{k: r.get(k) for k in STRUCT if k in r} for r in jl(ROOT / d / "think_ledger.jsonl")]
        comps = jl(ROOT / d / "compactions.jsonl")
        runs = collections.defaultdict(list)
        for r in led:
            runs[(r.get("arm"), r.get("task"))].append(r)
        n_err = sum(1 for r in led if "ledger_error" in r)
        n_callerr = sum(1 for r in led if r.get("call_error"))
        tools = [r for r in led if r.get("has_tools")]
        notools = [r for r in led if not r.get("has_tools") and "ledger_error" not in r]
        nonmono = sum(1 for rs in runs.values() for a, b in zip(rs, rs[1:]) if (b.get("t0") or 0) < (a.get("t0") or 0))
        print(f"== {name}: ledger {len(led)} records, {len(runs)} task-runs, tool-bearing {len(tools)}, "
              f"without tools {len(notools)}, ledger_error {n_err}, call_error {n_callerr}, non-monotonic t0 {nonmono}")
        comp_err = sum(1 for c in comps if c.get("error"))
        per_run = collections.Counter((c.get("arm"), c.get("task")) for c in comps)
        print(f"   compactions {len(comps)} (error {comp_err}); task-runs with >=1: {len(per_run)}; "
              f"per-run counts {sorted(collections.Counter(per_run.values()).items())}; "
              f"compaction keys {sorted(comps[0]) if comps else []}")
        unmatched = [c for c in comps if (c.get("arm"), c.get("task")) not in runs]
        print(f"   compaction records with no ledger task-run: {len(unmatched)}")
        # Alignment: does a ledger request without tools overlap each compaction window?
        hit = 0
        for c in comps:
            rs = runs.get((c.get("arm"), c.get("task")), [])
            if any(not r.get("has_tools") and "ledger_error" not in r and r.get("t0") is not None and r.get("t1") is not None
                   and r["t0"] <= c["t1"] + 1.0 and r["t1"] >= c["t0"] - 1.0 for r in rs):
                hit += 1
        print(f"   compactions overlapped by a no-tools ledger request (+-1 s): {hit}/{len(comps)}")
        # Boundary structure around the FIRST compaction of each run (completed tool-bearing calls only).
        drops = same_or_up = no_pre = no_post = 0
        js = []
        gaps = []
        for key, rs in runs.items():
            cs = sorted((c for c in comps if (c.get("arm"), c.get("task")) == key and not c.get("error")),
                        key=lambda c: c["t0"])
            if not cs:
                continue
            c = cs[0]
            comp = [r for r in rs if r.get("has_tools") and not r.get("call_error") and r.get("finish_reason") is not None
                    and "ledger_error" not in r]
            pre = [r for r in comp if r["t1"] <= c["t0"]]
            post = [r for r in comp if r["t0"] >= c["t1"]]
            mid = [r for r in comp if not (r["t1"] <= c["t0"] or r["t0"] >= c["t1"])]
            if mid:
                gaps.append(len(mid))
            if not pre:
                no_pre += 1
                continue
            if not post:
                no_post += 1
                continue
            js.append(len(pre))
            if post[0]["n_messages"] < pre[-1]["n_messages"]:
                drops += 1
            else:
                same_or_up += 1
        print(f"   first compaction: n_messages drops at boundary {drops}, does not drop {same_or_up}, "
              f"no completed call before {no_pre}, none after {no_post}, calls overlapping the compaction window "
              f"{sum(gaps)} in {len(gaps)} runs")
        print(f"   boundary index j (completed calls before first compaction): {sorted(collections.Counter(js).items())}")
        if name == "E8":
            # Show the structure of the first two compacted runs (no reasoning fields).
            shown = 0
            for key, rs in runs.items():
                cs = sorted((c for c in comps if (c.get("arm"), c.get("task")) == key), key=lambda c: c["t0"])
                if not cs or shown >= 2:
                    continue
                shown += 1
                t00 = rs[0]["t0"]
                ev = [(r["t0"] - t00, "call", r) for r in rs] + [(c["t0"] - t00, "COMPACTION", c) for c in cs]
                print(f"   -- example {key}:")
                for t, kind, x in sorted(ev, key=lambda e: e[0]):
                    if kind == "call":
                        print(f"      {t:7.1f}s call tools={int(bool(x.get('has_tools')))} n_messages={x.get('n_messages')} "
                              f"hist_assistant={x.get('hist_assistant')} dur={x['t1'] - x['t0']:.1f}s")
                    else:
                        print(f"      {t:7.1f}s COMPACTION dur={x['t1'] - x['t0']:.1f}s n_events={x.get('n_events')} "
                              f"summary_chars={x.get('summary_chars')}")


if __name__ == "__main__":
    main()
