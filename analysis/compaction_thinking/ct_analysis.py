"""Does Gemma 4 think less after the harness compacts its history? Post-hoc analysis of the E7, E8 and E9 runs.

Frozen plan: PLAN.md. This file, its tests, the probe and the inputs are hashed in FREEZE.json before the first real run.
Usage (from this folder):
  python -I -B -X utf8 ct_analysis.py --checks-only        structural checks V1-V3; reasoning fields are discarded on load
  python -I -B -X utf8 ct_analysis.py --standin null|drop  synthetic reasoning fields on the real structure -> validation/
  python -I -B -X utf8 ct_analysis.py                      the real analysis; refuses to run unless FREEZE.json verifies
Standard library only.
"""
import argparse
import collections
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SETS = {"E7": "audit/e7/e7_output", "E8": "audit/e8/e8_output", "E9": "audit/e9_runtime_pilot/e9_output"}
EXPECTED = {"E7": (1284, 60), "E8": (2703, 120), "E9": (535, 27)}  # (ledger records, compaction records), probe
K_MAIN = 3
K_SENS = (1, 5)
MATCH_ORDER = (0, -1, 1, -2, 2)
B = 2000
SEED = 20261031
DROP = 0.10
OFFSETS = tuple(range(-5, 5))
REASONING_FIELDS = ("reasoning_chars", "reasoning_text", "hist_with_reasoning", "hist_reasoning_chars",
                    "reasoning_tokens_usage")


# ---------------------------------------------------------------- loading
def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def is_completed(r):
    """E6R's unit: a ledger record with tools, no call error, a finish_reason and no ledger error."""
    return bool(r.get("has_tools")) and not r.get("call_error") and r.get("finish_reason") is not None \
        and "ledger_error" not in r


class Run:
    def __init__(self, key, records, attempts):
        self.key = key  # (set, arm, task)
        self.records = sorted(records, key=lambda r: r.get("t0") or 0.0)
        self.calls = [r for r in self.records if is_completed(r)]
        self.attempts = sorted(attempts, key=lambda c: c["t0"])
        # Position of an attempt = number of completed calls that ended at or before its start; it sits between
        # call p-1 and call p.
        self.att_pos = [sum(1 for r in self.calls if r["t1"] <= c["t0"]) for c in self.attempts]
        self.ok = [i for i, c in enumerate(self.attempts) if not c.get("error")]

    def first_ok(self):
        return self.att_pos[self.ok[0]] if self.ok else None


def load(set_name, d, strip=False):
    led = jl(ROOT / d / "think_ledger.jsonl")
    comps = jl(ROOT / d / "compactions.jsonl")
    if strip:
        for r in led:
            for f in REASONING_FIELDS:
                r.pop(f, None)
    groups = collections.defaultdict(list)
    for r in led:
        groups[(r.get("arm"), r.get("task"))].append(r)
    cgroups = collections.defaultdict(list)
    for c in comps:
        cgroups[(c.get("arm"), c.get("task"))].append(c)
    runs = [Run((set_name,) + key, recs, cgroups.get(key, [])) for key, recs in sorted(groups.items())]
    return led, comps, runs


def apply_standin(data, mode, seed=SEED):
    """Replace reasoning fields with synthetic values. 'null': thinking 90 % everywhere. 'drop': 60 % on the five
    completed calls after every successful compaction (and no thoughts left in their history), 90 % elsewhere."""
    rng = random.Random(seed + (1 if mode == "drop" else 0))
    for s in SETS:
        for run in data[s][2]:
            post = set()
            if mode == "drop":
                for i in run.ok:
                    p = run.att_pos[i]
                    post.update(range(p, p + 5))
            for t, r in enumerate(run.calls):
                th = rng.random() < (0.6 if t in post else 0.9)
                r["reasoning_chars"] = int(rng.lognormvariate(6.0, 1.0)) + 1 if th else 0
                r["hist_with_reasoning"] = 0 if t in post else (r.get("hist_assistant") or 0)


# ---------------------------------------------------------------- structural checks (no reasoning field used)
def structural_checks(data):
    res = {}
    bad = {s: (len(data[s][0]), len(data[s][1])) for s in SETS if (len(data[s][0]), len(data[s][1])) != EXPECTED[s]}
    res["V1"] = (not bad, "ledger and compaction counts as recorded before the freeze" if not bad
                 else f"count mismatch (ledger, compactions): {bad}")
    total = miss_map = miss_overlap = 0
    for s in SETS:
        led, comps, runs = data[s]
        byk = {r.key[1:]: r for r in runs}
        for c in comps:
            total += 1
            run = byk.get((c.get("arm"), c.get("task")))
            if run is None:
                miss_map += 1
                continue
            if not any(not r.get("has_tools") and "ledger_error" not in r and r.get("t0") is not None
                       and r.get("t1") is not None and r["t0"] <= c["t1"] + 1.0 and r["t1"] >= c["t0"] - 1.0
                       for r in run.records):
                miss_overlap += 1
    res["V2"] = (miss_map == 0 and miss_overlap == 0,
                 f"{total} compactions; without a ledger task-run {miss_map}; without an overlapping summary request "
                 f"{miss_overlap}")
    n = nodrop = overlap = 0
    for s in SETS:
        for run in data[s][2]:
            for i in run.ok:
                c = run.attempts[i]
                overlap += sum(1 for r in run.calls if r["t0"] < c["t1"] and r["t1"] > c["t0"])
            j = run.first_ok()
            if j is None or j == 0 or j >= len(run.calls):
                continue
            n += 1
            if not run.calls[j]["n_messages"] < run.calls[j - 1]["n_messages"]:
                nodrop += 1
    res["V3"] = (nodrop == 0 and overlap == 0,
                 f"{n} first compactions with calls on both sides; n_messages not dropping {nodrop}; completed calls "
                 f"overlapping a compaction {overlap}")
    return res


# ---------------------------------------------------------------- windows
def event(run, k):
    """The run's first successful compaction as an event with k completed calls on each side: (j, None) or
    (None, reason). j is the index of the first completed call after the compaction."""
    if not run.ok:
        return None, "no compaction"
    i = run.ok[0]
    j = run.att_pos[i]
    if j - k < 0 or j + k > len(run.calls):
        return None, "window incomplete"
    if any(j - k < p < j + k for x, p in enumerate(run.att_pos) if x != i):
        return None, "another compaction attempt inside the window"
    return j, None


def control_ok(run, j, k):
    """Calls [j-k, j+k) form a control window at index j: complete, no compaction attempt inside it or at its middle,
    and no successful compaction before it (the history was never compacted)."""
    if j - k < 0 or j + k > len(run.calls):
        return False
    for x, p in enumerate(run.att_pos):
        if j - k < p < j + k:
            return False
        if p <= j - k and not run.attempts[x].get("error"):
            return False
    return True


def thinking(r):
    return 1.0 if (r.get("reasoning_chars") or 0) > 0 else 0.0


def logchars(r):
    return math.log1p(r.get("reasoning_chars") or 0)


def prepost(run, j, k, f):
    return (sum(f(r) for r in run.calls[j - k:j]) / k, sum(f(r) for r in run.calls[j:j + k]) / k)


def unit_values(runs, k, f):
    ev, ctl = {}, {}
    for ri, run in enumerate(runs):
        j, _ = event(run, k)
        if j is not None:
            ev[ri] = (j, prepost(run, j, k, f))
        ctl[ri] = {jj: prepost(run, jj, k, f) for jj in range(k, len(run.calls) - k + 1) if control_ok(run, jj, k)}
    return ev, ctl


def did(ev, ctl, weights):
    """Difference in differences with run weights (multiplicities). Returns a dict, est None if nothing matched."""
    spre, spost, cnt = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
    for ri, cj in ctl.items():
        w = weights.get(ri, 0)
        if not w:
            continue
        for j, (a, b) in cj.items():
            spre[j] += w * a
            spost[j] += w * b
            cnt[j] += w
    num = den = epre = epost = cpre = cpost = 0.0
    unmatched = 0
    for ri, (j, (a, b)) in ev.items():
        w = weights.get(ri, 0)
        if not w:
            continue
        jm = next((j + o for o in MATCH_ORDER if cnt.get(j + o, 0) > 0), None)
        if jm is None:
            unmatched += w
            continue
        ca, cb = spre[jm] / cnt[jm], spost[jm] / cnt[jm]
        num += w * ((b - a) - (cb - ca))
        den += w
        epre, epost, cpre, cpost = epre + w * a, epost + w * b, cpre + w * ca, cpost + w * cb
    if not den:
        return {"est": None, "matched": 0, "unmatched": unmatched}
    return {"est": num / den, "matched": den, "unmatched": unmatched, "event_pre": epre / den,
            "event_post": epost / den, "control_pre": cpre / den, "control_post": cpost / den}


def quantile(sorted_vals, q):
    return sorted_vals[int(round(q * (len(sorted_vals) - 1)))]


def bootstrap(n_runs, ev, ctl, b=B, seed=SEED):
    """Cluster bootstrap over task-runs: percentile 95 % interval of the DiD."""
    rng = random.Random(seed)
    idx = list(range(n_runs))
    vals = []
    for _ in range(b):
        w = collections.Counter(rng.choices(idx, k=n_runs))
        e = did(ev, ctl, w)["est"]
        if e is not None:
            vals.append(e)
    if not vals:
        return None, None, 0
    vals.sort()
    return quantile(vals, 0.025), quantile(vals, 0.975), len(vals)


def estimate(runs, k, f, b=B):
    ev, ctl = unit_values(runs, k, f)
    r = did(ev, ctl, {i: 1 for i in range(len(runs))})
    r["ci95"] = list(bootstrap(len(runs), ev, ctl, b=b)[:2])
    r["n_events"] = len(ev)
    return r


def label(est, lo, hi):
    if est is None or lo is None:
        return "NOT EVALUABLE"
    if est <= -DROP and hi < 0:
        return "THINKING DROPS AFTER COMPACTION"
    if lo > -DROP:
        return "NO MEANINGFUL DROP"
    return "UNCLEAR"


# ---------------------------------------------------------------- descriptive parts
def mechanism(runs, k):
    rows = []
    for run in runs:
        j, _ = event(run, k)
        if j is not None:
            a, b = run.calls[j - 1], run.calls[j]
            rows.append(((a.get("hist_assistant") or 0, a.get("hist_with_reasoning") or 0),
                         (b.get("hist_assistant") or 0, b.get("hist_with_reasoning") or 0)))
    if not rows:
        return {}

    def summ(pairs):
        n = len(pairs)
        return {"n": n, "mean_hist_assistant": sum(h for h, _ in pairs) / n,
                "mean_hist_with_reasoning": sum(w for _, w in pairs) / n,
                "share_no_thoughts_in_history": sum(1 for _, w in pairs if w == 0) / n,
                "share_all_turns_with_thoughts": sum(1 for h, w in pairs if h > 0 and w == h) / n,
                "hist_with_reasoning_counts": dict(sorted(collections.Counter(w for _, w in pairs).items()))}
    return {"last_call_before": summ([x for x, _ in rows]), "first_call_after": summ([y for _, y in rows])}


def event_study(runs, k):
    """Thinking rate and mean reasoning characters by offset from the boundary, for the primary events, and for
    never-compacted calls at the same absolute index in the other runs (each event weighted equally)."""
    uncompacted = collections.defaultdict(list)  # index -> [(run index, call)]
    for ri, run in enumerate(runs):
        f = run.first_ok()
        for t, c in enumerate(run.calls):
            if f is None or t < f:
                uncompacted[t].append((ri, c))
    evs = [(ri, run, event(run, k)[0]) for ri, run in enumerate(runs)]
    evs = [(ri, run, j) for ri, run, j in evs if j is not None]
    rows = []
    for o in OFFSETS:
        rt, rc, ct, cc, n_ev, n_ctl_ev = [], [], [], [], 0, 0
        for ri, run, j in evs:
            t = j + o
            i0 = run.ok[0]
            other = [p for x, p in enumerate(run.att_pos) if x != i0]
            if 0 <= t < len(run.calls) and not any((t < p < j) if o < 0 else (j < p <= t) for p in other):
                rt.append(thinking(run.calls[t]))
                rc.append(run.calls[t].get("reasoning_chars") or 0)
                n_ev += 1
            pool = [c for rj, c in uncompacted.get(t, []) if rj != ri]
            if pool:
                ct.append(sum(thinking(c) for c in pool) / len(pool))
                cc.append(sum((c.get("reasoning_chars") or 0) for c in pool) / len(pool))
                n_ctl_ev += 1
        rows.append({"offset": o, "events_n": n_ev, "events_thinking_rate": sum(rt) / len(rt) if rt else None,
                     "events_mean_reasoning_chars": sum(rc) / len(rc) if rc else None, "controls_events_n": n_ctl_ev,
                     "controls_thinking_rate": sum(ct) / len(ct) if ct else None,
                     "controls_mean_reasoning_chars": sum(cc) / len(cc) if cc else None})
    return rows


def all_compactions_raw(runs, k):
    pre = post = n = 0.0
    for run in runs:
        for i in run.ok:
            j = run.att_pos[i]
            if j - k < 0 or j + k > len(run.calls):
                continue
            if any(j - k < p < j + k for x, p in enumerate(run.att_pos) if x != i):
                continue
            a, b = prepost(run, j, k, thinking)
            pre, post, n = pre + a, post + b, n + 1
    return {"n_compactions": int(n), "thinking_rate_before": pre / n if n else None,
            "thinking_rate_after": post / n if n else None}


def analyze(data, b=B):
    runs = [r for s in SETS for r in data[s][2]]
    acc = collections.Counter()
    for run in runs:
        j, why = event(run, K_MAIN)
        acc["event" if j is not None else why] += 1
    out = {"n_runs": len(runs), "n_completed_calls": sum(len(r.calls) for r in runs),
           "event_accounting_k3": dict(sorted(acc.items()))}
    prim = estimate(runs, K_MAIN, thinking, b=b)
    out["primary_thinking_k3"] = prim
    out["label"] = label(prim["est"], *prim["ci95"])
    ln = estimate(runs, K_MAIN, logchars, b=b)
    pct = (lambda v: None if v is None else math.exp(v) - 1)
    out["secondary_reasoning_length_k3"] = dict(ln, change_pct=pct(ln["est"]), ci95_pct=[pct(v) for v in ln["ci95"]])
    out["sensitivity_k"] = {str(k): estimate(runs, k, thinking, b=b) for k in K_SENS}
    out["per_set_k3"] = {s: estimate(data[s][2], K_MAIN, thinking, b=b) for s in SETS}
    out["mechanism_k3"] = mechanism(runs, K_MAIN)
    out["event_study"] = event_study(runs, K_MAIN)
    out["all_compactions_raw_k3"] = all_compactions_raw(runs, K_MAIN)
    out["ceiling_note"] = prim.get("event_pre") is not None and prim["event_pre"] >= 0.97
    return out


# ---------------------------------------------------------------- output
def fmt(v, pct=False):
    if v is None:
        return "n/a"
    return f"{100 * v:+.1f} pts" if pct else f"{v:.3f}"


def fmt_rel(v):
    return "n/a" if v is None else f"{100 * v:+.1f}%"


def table(out):
    p = out["primary_thinking_k3"]
    ln = out["secondary_reasoning_length_k3"]
    lines = ["# Compaction-thinking analysis: results", "",
             f"- **Label (PLAN.md section 6): {out['label']}**",
             f"- Runs {out['n_runs']}, completed tool-bearing calls {out['n_completed_calls']}; events (k = 3): "
             f"{out['event_accounting_k3']}",
             f"- Ceiling note (thinking rate before compaction >= 0.97): {out['ceiling_note']}", "",
             "| Measure (k = 3) | Events before | Events after | Controls before | Controls after | DiD | 95% CI |",
             "|---|---|---|---|---|---|---|",
             f"| Thinking active (share of calls) | {fmt(p.get('event_pre'))} | {fmt(p.get('event_post'))} | "
             f"{fmt(p.get('control_pre'))} | {fmt(p.get('control_post'))} | {fmt(p['est'], True)} | "
             f"{fmt(p['ci95'][0], True)} to {fmt(p['ci95'][1], True)} |",
             f"| Reasoning length, mean log(1 + chars) | {fmt(ln.get('event_pre'))} | {fmt(ln.get('event_post'))} | "
             f"{fmt(ln.get('control_pre'))} | {fmt(ln.get('control_post'))} | "
             f"{fmt_rel(ln['change_pct'])} (relative change) | {fmt_rel(ln['ci95_pct'][0])} to "
             f"{fmt_rel(ln['ci95_pct'][1])} |", "",
             f"Matched events {p['matched']:.0f}, unmatched {p['unmatched']:.0f}.", "",
             "## Sensitivity (descriptive)", "", "| Window k / set | Events | DiD thinking | 95% CI |", "|---|---|---|---|"]
    for k, r in out["sensitivity_k"].items():
        lines.append(f"| k = {k} | {r['n_events']} | {fmt(r['est'], True)} | {fmt(r['ci95'][0], True)} to "
                     f"{fmt(r['ci95'][1], True)} |")
    for s, r in out["per_set_k3"].items():
        lines.append(f"| {s} (k = 3) | {r['n_events']} | {fmt(r['est'], True)} | {fmt(r['ci95'][0], True)} to "
                     f"{fmt(r['ci95'][1], True)} |")
    m = out["mechanism_k3"]
    if m:
        lines += ["", "## Thoughts left in the history (descriptive)", "",
                  "| Call | Mean assistant turns | Mean turns with thoughts | No thoughts | All turns with thoughts |",
                  "|---|---|---|---|---|"]
        for name, key in (("Last call before", "last_call_before"), ("First call after", "first_call_after")):
            x = m[key]
            lines.append(f"| {name} | {x['mean_hist_assistant']:.2f} | {x['mean_hist_with_reasoning']:.2f} | "
                         f"{x['share_no_thoughts_in_history']:.3f} | {x['share_all_turns_with_thoughts']:.3f} |")
    a = out["all_compactions_raw_k3"]
    lines += ["", f"All successful compactions with complete windows (raw, no control): n = {a['n_compactions']}, "
              f"thinking {fmt(a['thinking_rate_before'])} before vs {fmt(a['thinking_rate_after'])} after.", "",
              "Event study by offset: `event_study.csv`. Everything: `results.json`."]
    return "\n".join(lines) + "\n"


def verify_freeze():
    fz = HERE / "FREEZE.json"
    if not fz.exists():
        return False, "FREEZE.json missing"
    frozen = json.loads(fz.read_text(encoding="utf-8"))["sha256"]
    bad = [k for k, v in frozen.items() if not (ROOT / k).exists()
           or hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != v]
    return not bad, ("ALL MATCH" if not bad else f"MISMATCH {bad}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks-only", action="store_true")
    ap.add_argument("--standin", choices=["null", "drop"])
    a = ap.parse_args(argv)
    print(f"python {sys.version.split()[0]}")
    strip = a.checks_only or a.standin is not None
    data = {s: load(s, d, strip=strip) for s, d in SETS.items()}
    chk = structural_checks(data)
    for name, (ok, msg) in chk.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}: {msg}")
    if not all(ok for ok, _ in chk.values()):
        print("A structural check failed: no outcome computed.")
        return 2
    if a.checks_only:
        return 0
    if a.standin:
        apply_standin(data, a.standin)
        outdir = HERE / "validation" / f"standin_{a.standin}"
        outdir.mkdir(parents=True, exist_ok=True)
    else:
        ok, msg = verify_freeze()
        print(f"FREEZE {msg}")
        if not ok:
            return 3
        outdir = HERE
    out = analyze(data)
    (outdir / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (outdir / "RESULTS_TABLE.md").write_text(table(out), encoding="utf-8")
    cols = list(out["event_study"][0])
    (outdir / "event_study.csv").write_text(
        "\n".join([",".join(cols)] + [",".join("" if r[c] is None else str(r[c]) for c in cols)
                                      for r in out["event_study"]]) + "\n", encoding="utf-8")
    p = out["primary_thinking_k3"]
    print(f"LABEL {out['label']} | DiD {fmt(p['est'], True)} 95% CI {fmt(p['ci95'][0], True)} to "
          f"{fmt(p['ci95'][1], True)} | events {p['n_events']} matched {p['matched']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
