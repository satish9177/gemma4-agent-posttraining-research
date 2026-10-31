# Quit-rule what-if: results (2026-10-30)

- **Answer:** not supported by the existing runs. **No rule passes the screen** (PLAN.md section 6). Every rule that
  saves real time loses more solves than the time is worth; the rules that lose nothing save nothing.
- **Run:** `whatif.py` under `FREEZE.json` (v2, 183 files, verified ALL MATCH before the run), after amendment 1 (PLAN.md).
  Checks: V1 PASS (no-rule rows reproduce E9 section 8), V2 PASS (counted calls = harness tool_calls for every run),
  unit tests ALL PASS (`test_stdout.txt`). No solved run lacked a detected source edit.
- Outputs: `results.json` (every rule × set, with lost-solve task lists), `RESULTS_TABLE.md`, `runs.json` (per-call records),
  `whatif_stdout.txt`, `descriptive_stdout.txt`. The v1 run's outputs (failed V1, unread) are in `v1_failed_check/`.
- Post-hoc what-if; no registered verdict; changes no registered result (E7, E8, E9, E10).

## 1. Main table (7-minute what-if for E8; held-out sets at their recorded caps)
| Rule | E8 36 calls: fired / solves / P120 | E8 28 calls: fired / solves / P120 | E7: fired / solves lost | E9: fired / solves lost |
|---|---|---|---|---|
| no rule | 0 / **23** / 10.30 h | 0 / **20** / 10.32 h | 0 / 0 | 0 / 0 |
| F1(8) | 40 / 6 / 4.06 | 36 / 8 / 4.48 | 37 / 12 | 14 / 3 |
| F1(12) | 27 / 14 / 6.27 | 29 / 11 / 6.20 | 30 / 7 | 13 / 3 |
| F1(16) | 22 / 15 / 7.48 | 25 / 13 / 7.33 | 24 / 3 | 11 / 3 |
| F1(20) | 17 / 17 / 8.21 | 18 / 16 / 8.24 | 19 / 1 | 10 / 2 |
| F2(2) | 0 / 23 / 10.30 | 0 / 20 / 10.32 | 1 / 1 | 0 / 0 |
| F2(3), F2(4) | 0 / 23 / 10.30 | 0 / 20 / 10.32 | 0 / 0 | 0 / 0 |

All 31 rules are in `RESULTS_TABLE.md`. The F1+F2 combinations equal F1 alone except for one or two E7 runs, because F2
almost never fires. Screen criterion 1 needs ≥ 22 solves at ≤ 10.0 h on E8 36 calls: the best F1 rule keeps 17; the F2
rules keep 23 but save no time.

## 2. Why (descriptive, computed after the screen; `descriptive_stdout.txt`)
- **Solved runs often start editing late.** Budget call of the first source edit, solved runs:
  - E8 28 calls: median 11; 8 of 21 at call 16 or later (16, 17, 17, 19, 21, 23, 25, 27).
  - E8 36 calls: median 11; 7 of 24 after call 20 (22, 27, 28, 28, 29, 30, 30).
  - E7 28 calls: median 11; 3 of 19 at call 20 or later.
  The extra solves of the 36-call budget come largely from these slow starters, which is exactly what "no edit yet → stop"
  removes.
- **"No edit yet" does not separate the hopeless runs.** Unsolved runs that never edited: 12 of 27 (E8 28), 9 of 24
  (E8 36), 15 of 29 (E7). But at call 20, about a third of the runs with no edit yet still went on to solve (E8 36: F1(20)
  fires on 17 runs, 6 of them solved).
- **The agent almost never runs the test suite**, so F2 has nothing to fire on: median 0 pytest runs per task; 36, 33 and
  33 of 48 tasks have none (E8 28, E8 36, E7).

## 3. Limits
- Only two signals were tested (no edit yet; failing test streak). Others (repeated reads, loops, no progress after an
  edit) are untested, and testing many more on the same 96 runs would increase the risk of a chance fit.
- Paths are assumed unchanged until a rule fires; T 0.2 runs; 48 tasks from fastapi and rich.

## 4. What it suggests (judgement)
- Do not add an early-quit rule based on "no edit yet". On these runs it trades solves for time at a bad rate (E8 36
  calls, F1(20): 2.1 h saved for 6 of 23 solves).
- The runtime problem of the 36-call budget is not fixed by quitting early; it would need faster steps or fewer
  long-running tasks by some other route.
- Observation for the planned failure analysis, not tested here: the agent submits without running the existing tests in
  about 70 % of tasks.
