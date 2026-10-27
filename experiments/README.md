# Experiment ledger (E3–E9)

These are preregistered Gemma 4 agent evaluations, run 17–27 October 2026.

**Common setup:**
- **Model:** `gemma-4-31b-it` (QAT W4A16), served by vLLM 0.19.1 with tensor parallelism 4 on 4× NVIDIA L4.
- **Harness:** a function-calling repository-agent harness built on Google's Agent Development Kit, with nine tools and per-task sandboxes graded by hidden tests.
- **Panel:** paired experiments used a fixed 48-task development panel, sampled with a fixed seed from 101 gold-validated tasks in three public Python repositories. Pilots used subsets of it.

The protocol is in [docs/methodology.md](../docs/methodology.md).

Each folder has:
- `PREREGISTRATION.md`: a sanitized public summary of the frozen design and decision rules, with the SHA-256 and freeze time of the withheld original;
- `RESULTS.md`: validity, results, the registered verdict, post-hoc notes kept separate, limitations, and what changed;
- `metadata.json`: machine-readable settings and outcomes.

| ID | Topic | Thinking | Tasks | Registered outcome | Record |
|---|---|---|---|---|---|
| E3 | Tool-protocol reliability: read serialization (3 runs) | off | 48 | Run 1: *INCONCLUSIVE*. Confirmation: *INVALID* (server outage). Final: *E3 CONFIRMED* (12 → 15; corrupted calls 19.6% → 6.4%) | [e3](e3/RESULTS.md) |
| E4 | Tool-protocol reliability: edit protocol | off | 48 | *E4 TIE* (13 vs 14; edit-argument corruption 83 calls → 0) | [e4](e4/RESULTS.md) |
| E5 | Progress-rules prompt (anti-loop) pilot | off | 10 | *NO-GO* (no-progress calls 42.9% vs bar ≤ 29.5%) | [e5](e5/RESULTS.md) |
| E5G | Host-side progress guard pilot (research only) | off | 10 | *LOOPS REMOVED: NO* | [e5g](e5g/RESULTS.md) |
| E6R | Thinking-history retention, **mechanical pilot** | on (512) | 4 per arm | Thoughts dropped: *BROKEN* (thinking on 47% of calls). Thoughts kept: *MECHANICALLY CLEAN* (100%) | [e6r](e6r/RESULTS.md) |
| E7 | Strong inference-only baseline reproduction | on (4,096) | 48 | 19/48; *NOT PROMISING* (registered; criterion later found flawed, verdict unchanged) | [e7](e7/RESULTS.md) |
| E8 | Paired tool-call budget, 28 vs 36 | on (4,096) | 48 | 21 → 24/48, **exact McNemar p ≈ 0.25**; *E8 WIN*; mechanism *NOT CONFIRMED* | [e8](e8/RESULTS.md) |
| E9 | Runtime budget, 8 vs 7 minutes at 32 calls (stress-panel pilot) | on (4,096) | 8 | VALID; *MIXED* (7-minute arm: empty final patch on 4 tasks vs 0; all other conditions for preferring it passed). Solves 2 vs 3, not a criterion | [e9](e9/RESULTS.md) |

**Notes**
- **Not run:** E6A, a frozen sampling experiment, was held and never run. It is described in the E6R folder.
- **Earlier work:** runs before E3 used other configurations and are not part of this ledger.
- **Statistics:** no result in this ledger is statistically significant after accounting for multiple comparisons. Byte-identical configurations flip 2–4 of 48 tasks between runs ([results/](../results/README.md)).
- **Thinking off vs on:** thinking-off (E3–E5G) and thinking-on (E7–E9) runs differ in prompts and budgets as well as thinking. They are not a controlled thinking ablation.
