#!/usr/bin/env python3
"""Summarize the Tier A mining pilot. Frozen before any pilot candidate was validated. Standard library only.

Inputs: runs/P*/result.json, pilot_candidates.csv, ../tier_a_mining_candidates.csv (repository sizes of the pool).
Outputs: pilot_results.json and pilot_results.csv (one row per candidate, no logs).

Estimands
  * primary: repository-level conversion rate p = gold-valid / selected (one candidate per sampled repository),
    Wilson 95% interval;
  * secondary: candidate-weighted rate = sum(n_r * x_r) / sum(n_r) over sampled repositories (n_r = candidates of
    repository r in the pool), bootstrap 95% interval over repositories;
  * raw candidates needed for 150 / 200 / 250 / 300 Tier A tasks at p (point and interval), both for mined tasks
    alone and after crediting the 62 published candidates at the earlier keep rate (101/115);
  * projection under a per-repository cap c on candidates processed:
        G(c) = (R_pool / R_sample) * sum over sampled r of min(c, n_r) * x_r     (Horvitz-Thompson, equal-probability
    repository sampling), bootstrap 95% interval over sampled repositories; Tier A total = G(c) + 62 * 101/115;
  * diversity under cap c: largest single-repository share and effective number of repositories
        N_eff(c) = (sum_r min(c, n_r))^2 / sum_r min(c, n_r)^2  over the whole pool.

Cap recommendation rule (fixed before results): the smallest c in CAPS whose Tier A total reaches 250 at the lower
95% bound; if none, the smallest reaching 200 at the lower bound; if none, the smallest reaching 200 at the point
estimate (flagged "point estimate only"); if none, no cap reaches 200 and the realized N is the expected outcome.

    python -I analysis/tier_a_pilot/summarize_pilot.py
"""
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPS = [1, 2, 3, 5, 10, 20, 50]
TARGETS = [150, 200, 250, 300]
PUBLISHED, KEEP = 62, 101 / 115
SEED, REPS = 20261028, 2000
STAGES = ["S1_prepared", "S2_license", "S3_checkout", "S4_patches", "S5_environment", "S6_tests",
          "S7a_gold_makes_tests_pass", "S7b_gold_repeat", "S7c_empty_patch_fails_twice"]
LABELS = {"S1_prepared": "PR data, test patch, gold patch and a runnable test file",
          "S2_license": "open license",
          "S3_checkout": "repository cloned at the base commit",
          "S4_patches": "test and gold patches apply",
          "S5_environment": "environment built (install succeeded, pytest runs)",
          "S6_tests": "test results parsed with the gold patch",
          "S7a_gold_makes_tests_pass": "gold patch makes >= 1 previously failing test pass (run 1)",
          "S7b_gold_repeat": "same test passes again with the gold patch (run 2)",
          "S7c_empty_patch_fails_twice": "and fails again without it (run 2): gold-valid"}


def wilson(k, n, z=1.959964):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def q(xs, a):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(a * len(xs))))]


def main():
    rows = list(csv.DictReader(l for l in open(HERE / "pilot_candidates.csv", encoding="utf-8") if not l.startswith("#")))
    pool = defaultdict(int)
    for r in csv.DictReader(open(HERE.parent / "tier_a_mining_candidates.csv", encoding="utf-8")):
        if r["found_by"] == "known_buildable_complete":
            pool[r["repo"].lower()] += 1
    res = {}
    for r in rows:
        f = HERE / "runs" / r["pilot_id"] / "result.json"
        res[r["pilot_id"]] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    n_sel = len(rows)
    missing = [p for p, v in res.items() if v is None]

    funnel, alive = [{"step": "selected", "n": n_sel}], set(res)
    for s in STAGES:
        alive = {p for p in alive if res[p] and res[p]["stage"].get(s)}
        funnel.append({"step": s, "label": LABELS[s], "n": len(alive)})
    x = {r["pilot_id"]: int(bool(res[r["pilot_id"]] and res[r["pilot_id"]].get("gold_valid"))) for r in rows}
    n_r = {r["pilot_id"]: pool[r["repo"].lower()] for r in rows}
    k = sum(x.values())
    p = k / n_sel
    lo, hi = wilson(k, n_sel)

    rng = random.Random(SEED)
    ids = [r["pilot_id"] for r in rows]
    boots = [[rng.choice(ids) for _ in ids] for _ in range(REPS)]
    cw = sum(n_r[i] * x[i] for i in ids) / sum(n_r[i] for i in ids)
    cw_b = [sum(n_r[i] * x[i] for i in b) / sum(n_r[i] for i in b) for b in boots]

    expected_pub = PUBLISHED * KEEP
    need = {}
    for t in TARGETS:
        need[str(t)] = {
            "mined_only": {"point": math.ceil(t / p) if p else None,
                           "interval": [math.ceil(t / hi) if hi else None, math.ceil(t / lo) if lo else None]},
            "after_crediting_published_62": {"new_valid_needed": math.ceil(t - expected_pub),
                                             "point": math.ceil((t - expected_pub) / p) if p else None,
                                             "interval": [math.ceil((t - expected_pub) / hi) if hi else None,
                                                          math.ceil((t - expected_pub) / lo) if lo else None]}}

    R_pool, R_s = len(pool), n_sel
    sizes = list(pool.values())
    caps = []
    for c in CAPS + [None]:
        m = lambda n: n if c is None else min(c, n)  # noqa: E731
        G = R_pool / R_s * sum(m(n_r[i]) * x[i] for i in ids)
        Gb = [R_pool / R_s * sum(m(n_r[i]) * x[i] for i in b) for b in boots]
        cap_pool = sum(m(n) for n in sizes)
        caps.append({"cap": "none" if c is None else c, "pool_candidates_processed": cap_pool,
                     "projected_mined_gold_valid": round(G), "ci95": [round(q(Gb, 0.025)), round(q(Gb, 0.975))],
                     "projected_tier_a_total": round(G + expected_pub),
                     "tier_a_total_ci95": [round(q(Gb, 0.025) + expected_pub), round(q(Gb, 0.975) + expected_pub)],
                     "largest_repo_share": round(max(m(n) for n in sizes) / cap_pool, 4),
                     "effective_repositories": round(cap_pool ** 2 / sum(m(n) ** 2 for n in sizes), 1)})
    rec = None
    for target, key, label in ((250, 0, "lower 95% bound reaches 250"), (200, 0, "lower 95% bound reaches 200"),
                               (200, None, "point estimate reaches 200 (point estimate only)")):
        for row in caps[:-1]:
            val = row["tier_a_total_ci95"][0] if key == 0 else row["projected_tier_a_total"]
            if val >= target:
                rec = {"cap": row["cap"], "basis": label}
                break
        if rec:
            break

    def band(n):
        return "1" if n == 1 else "2-9" if n < 10 else "10-49" if n < 50 else "50+"

    by = lambda f: {g: {"n": len(v), "gold_valid": sum(x[i] for i in v)}  # noqa: E731
                    for g, v in sorted(_group(ids, f).items())}
    meta = {r["pilot_id"]: r for r in rows}
    out = {
        "selected": n_sel, "results_missing": missing, "funnel": funnel,
        "gold_valid": k, "repository_level_rate": round(p, 4), "repository_level_rate_wilson95": [round(lo, 4), round(hi, 4)],
        "candidate_weighted_rate": round(cw, 4), "candidate_weighted_rate_bootstrap95": [round(q(cw_b, .025), 4), round(q(cw_b, .975), 4)],
        "raw_candidates_needed": need, "expected_from_published_62": round(expected_pub, 1),
        "cap_projection": caps, "recommended_cap": rec,
        "pool": {"repositories": R_pool, "candidates": sum(sizes),
                 "repos_by_candidate_count": dict(Counter(band(n) for n in sizes))},
        "by_repo_size": by(lambda i: band(n_r[i])),
        "by_recipe": by(lambda i: (res[i] or {}).get("recipe_used") or "none"),
        "by_python": by(lambda i: (res[i] or {}).get("python") or "none"),
        "by_stars": by(lambda i: "<100" if int(meta[i]["stars"]) < 100 else "100-999" if int(meta[i]["stars"]) < 1000 else ">=1000"),
        "failure_reasons": dict(Counter((res[i] or {}).get("reason") or "gold-valid" for i in ids).most_common()),
        "hints_among_failures": {"network": sum(bool((res[i] or {}).get("hint_network")) for i in ids if not x[i]),
                                 "hardware": sum(bool((res[i] or {}).get("hint_hardware")) for i in ids if not x[i])},
        "flaky_tests_total": sum(((res[i] or {}).get("classification") or {}).get("flaky", 0) for i in ids),
        "f2p_per_valid_task_median": sorted(((res[i] or {}).get("classification") or {}).get("f2p_stable", 0)
                                            for i in ids if x[i])[k // 2] if k else None,
        "cpu_seconds_total_wall": round(sum((res[i] or {}).get("seconds", 0) for i in ids)),
    }
    (HERE / "pilot_results.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "pilot_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pilot_id", "repo", "pr_number", "candidates_in_repo", "gold_valid", "last_stage_passed", "reason",
                    "recipe_used", "python", "f2p_stable", "p2p_stable", "flaky", "seconds"])
        for i in ids:
            r = res[i] or {}
            last = max((s for s in STAGES if r.get("stage", {}).get(s)), key=STAGES.index, default="")
            c = r.get("classification") or {}
            w.writerow([i, meta[i]["repo"], meta[i]["pr_number"], n_r[i], x[i], last, r.get("reason") or "",
                        r.get("recipe_used") or "", r.get("python") or "", c.get("f2p_stable", ""),
                        c.get("p2p_stable", ""), c.get("flaky", ""), r.get("seconds", "")])
    print(json.dumps({k_: out[k_] for k_ in ("gold_valid", "repository_level_rate", "repository_level_rate_wilson95",
                                              "candidate_weighted_rate", "recommended_cap")}, indent=1))


def _group(ids, f):
    g = defaultdict(list)
    for i in ids:
        g[f(i)].append(i)
    return g


if __name__ == "__main__":
    main()
