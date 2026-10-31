# Compaction-thinking analysis: results (2026-10-31)

- **Answer (label fixed in PLAN.md section 6): NO MEANINGFUL DROP.** Thinking stayed on after the harness compacted the
  history. In the three calls before the first compaction 100.0% of calls carried reasoning, and 99.7% in the three
  after; never-compacted histories at the same call index went from 99.8% to 99.9%. Difference −0.3 points, 95% interval
  −1.0 to 0.0. A drop of more than about 1 point is ruled out.
- **Run:** `ct_analysis.py` under `FREEZE.json` (22 files, frozen 2026-10-31T17:33:01Z, verified ALL MATCH just before
  the run). Checks V1–V3 PASS in the run; V4–V5 passed before the freeze (PLAN.md section 9). Python 3.13.15. Outputs:
  `results.json`, `RESULTS_TABLE.md`, `event_study.csv`, `run_stdout.txt`.
- Post-hoc analysis of existing runs. Not a registered verdict; changes no registered result (E3–E10).

## 1. Main table (k = 3; 124 events, all matched)
| Measure | Events before | Events after | Controls before | Controls after | Difference | 95% interval |
|---|---|---|---|---|---|---|
| Thinking active (share of calls) | 1.000 | 0.997 | 0.998 | 0.999 | −0.3 points | −1.0 to 0.0 |
| Reasoning length, mean log(1 + chars) | 5.936 | 5.286 | 5.118 | 5.178 | −50.8% | −63.0% to −33.1% |

Event accounting: 160 task-runs; 124 events; 27 runs never compacted; 8 windows incomplete; 1 with another attempt inside.

## 2. Descriptive (pre-stated in PLAN.md section 5, never part of the label)
- **Ceiling:** thinking was on in ≥ 97% of calls before compaction (ceiling note true). By the plan, the length measure
  then carries more of the reading.
- **Thoughts survive compaction:** the first request after compaction carried 3 earlier assistant turns in every event,
  and all 3 carried their thoughts in every event. Before compaction: 13.87 turns, 13.86 with thoughts. The history was
  never thought-free.
- **Sensitivity:** k = 1: 0.0 points; k = 5: −0.6 points (−1.4 to −0.1); E7 0.0, E8 −0.6, E9 0.0. All far inside ±10.
- **All 177 successful compactions** with complete windows: thinking 100.0% before vs 99.8% after (raw).
- **Reasoning length by call (`event_study.csv`):** reasoning was unusually long just before compaction (mean 2,524
  characters at offset −2 and 1,404 at −1, against 808–844 in controls) and near or above the control level afterwards
  (804, 1,064 and 1,103 characters at offsets 0 to +2, against 760–770).

## 3. Reading (judgement, written after the results)
- **The pre-stated question has a clear answer:** in these runs, the harness's compaction does not switch thinking off.
- **Consistent with E6R:** E6R's fade happened when no earlier thoughts were in the history. Here compaction kept the
  thoughts on the three retained turns, and thinking stayed on. A few recent turns that carry thoughts appear to be
  enough. This is observational, and the settings differ from E6R (T 0.2 and budget 4,096 here; T 1.0 and budget 512 there).
- **The length difference is mostly the end of a spike before compaction, not a shortfall after it.** A likely
  selection effect: compaction fires when the prompt passes 14,336 tokens, and kept thoughts count toward the prompt,
  so calls with long reasoning (or large tool outputs) bring compaction forward. This is the non-randomized limitation
  stated in PLAN.md section 8, so the −50.8% should not be read as compaction shortening the thinking. After compaction,
  reasoning length is at or slightly above that of never-compacted histories. This explanation was not tested here.
- **For the paper:** thinking survives the harness's compaction because the retained turns keep their thoughts. Together
  with E6R, the practical rule for harness builders is: when compacting or summarizing, keep the reasoning on the turns
  that remain.

## 4. Limits
- As in PLAN.md section 8 (not randomized; compaction also shortens the context; T 0.2 / budget 4,096; fastapi and rich
  tasks; task-runs, not tasks, as clusters).
- With thinking near 100%, the share measure shows that compaction did not switch thinking off at these settings. It does
  not show that thoughts in the history never matter; E6R is the evidence for that.
