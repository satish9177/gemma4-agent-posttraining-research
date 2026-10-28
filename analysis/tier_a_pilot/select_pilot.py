#!/usr/bin/env python3
"""Select the Tier A mining-pilot sample. Offline, deterministic, standard library only.

Pool: every candidate in ../tier_a_mining_candidates.csv found by the complete enumeration of the
known-buildable universe (found_by == known_buildable_complete). No other information is used: no issue
text, no patch content, no model output, no environment information.

Procedure (frozen):
  1. Sort the pool's repositories by lower-case owner/name.
  2. rng = random.Random(SEED); draw N_REPOS repositories with rng.sample (uniform, without replacement).
  3. Visit the drawn repositories in sorted order; within each, sort its candidates by PR number and draw
     one with rng.choice.
If the pool has fewer than N_REPOS repositories, every repository is taken once and the shortfall is
recorded in the output header (no other rule changes).

    python -I analysis/tier_a_pilot/select_pilot.py
"""
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

SEED = 20261028
N_REPOS = 150
HERE = Path(__file__).resolve().parent
POOL = HERE.parent / "tier_a_mining_candidates.csv"
OUT = HERE / "pilot_candidates.csv"


def main():
    rows = [r for r in csv.DictReader(open(POOL, encoding="utf-8")) if r["found_by"] == "known_buildable_complete"]
    by_repo = defaultdict(list)
    for r in rows:
        by_repo[r["repo"].lower()].append(r)
    repos = sorted(by_repo)
    rng = random.Random(SEED)
    k = min(N_REPOS, len(repos))
    drawn = sorted(rng.sample(repos, k))
    picks = []
    for repo in drawn:
        cands = sorted(by_repo[repo], key=lambda r: int(r["pr_number"]))
        picks.append((rng.choice(cands), len(cands)))
    pool_sha = hashlib.sha256(POOL.read_bytes()).hexdigest()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write(f"# pool={POOL.name} sha256={pool_sha} pool_candidates={len(rows)} pool_repos={len(repos)} "
                f"seed={SEED} n_repos_requested={N_REPOS} n_repos_drawn={k}\n")
        w = csv.writer(f)
        w.writerow(["pilot_id", "repo", "pr_number", "pr_url", "pr_created_utc", "candidates_in_repo",
                    "spdx_license", "stars", "issue_post_release", "benchmark_subset_shape"])
        for i, (r, n) in enumerate(picks, 1):
            w.writerow([f"P{i:03d}", r["repo"], r["pr_number"], r["pr_url"], r["pr_created_utc"], n,
                        r["spdx_license"], r["stars"], r["issue_post_release"], r["benchmark_subset_shape"]])
    print(f"pool: {len(rows)} candidates in {len(repos)} repositories; drew {k} repositories (seed {SEED}) -> {OUT.name}")


if __name__ == "__main__":
    main()
