"""Recompute every paired comparison and run-to-run flip count reported in this repository
from results/per_task_outcomes_anonymized.csv. Standard library only.

    python analysis/verify_paired_stats.py

Exact McNemar p-values are two-sided binomial tests on the discordant pairs (p = 0.5).
They are descriptive: the registered decision rules of each experiment are in experiments/*/PREREGISTRATION.md.
"""
import csv
from math import comb
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "results" / "per_task_outcomes_anonymized.csv"

# Registered paired comparisons (control, treatment) on the fixed 48-task panel.
PAIRED = [
    ("E3 run 1", "E3R1_CONTROL", "E3R1_TREATMENT"),
    ("E3 final", "E3F_CONTROL", "E3F_TREATMENT"),
    ("E4", "E4_CONTROL", "E4_TREATMENT"),
    ("E8", "E8_CONTROL", "E8_TREATMENT"),
]
# Runs of byte-identical agent configurations (run-to-run noise).
IDENTICAL = [
    ("E3-treatment config: E3 run 1 vs E3 final", "E3R1_TREATMENT", "E3F_TREATMENT"),
    ("E3-treatment config: E3 final vs E4 control", "E3F_TREATMENT", "E4_CONTROL"),
    ("E3-treatment config: E3 run 1 vs E4 control", "E3R1_TREATMENT", "E4_CONTROL"),
    ("E7 config: E7 vs E8 control", "E7", "E8_CONTROL"),
]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
assert len(rows) == 48, len(rows)
col = lambda name: [int(r[name]) for r in rows]

print("solved / 48:")
for name in rows[0]:
    if name != "task":
        print(f"  {name:16s} {sum(col(name)):2d}")

print("\npaired comparisons (both / control-only / treatment-only / neither, exact McNemar p, descriptive):")
for label, c, t in PAIRED:
    a, b = col(c), col(t)
    both = sum(x and y for x, y in zip(a, b))
    c_only = sum(x and not y for x, y in zip(a, b))
    t_only = sum(y and not x for x, y in zip(a, b))
    neither = 48 - both - c_only - t_only
    print(f"  {label:10s} {sum(a):2d} -> {sum(b):2d}  delta {sum(b) - sum(a):+d} | "
          f"{both}/{c_only}/{t_only}/{neither} | p = {mcnemar_exact(c_only, t_only):.4g}")

print("\nidentical configurations, separate runs (tasks whose outcome flipped):")
for label, x, y in IDENTICAL:
    a, b = col(x), col(y)
    flips = sum(u != v for u, v in zip(a, b))
    print(f"  {label:45s} {sum(a):2d} vs {sum(b):2d} | flips {flips}")
