# Does thinking fade after history compaction? (post-hoc analysis, 31 October 2026)

- **Type:** a post-hoc analysis of existing runs (E7, E8, E9), frozen before any thinking outcome was computed. It is not
  an experiment: its label was fixed in advance but is not a registered verdict, and it changes no registered result.
- **Result: NO MEANINGFUL DROP.** In the three calls before a task's first compaction, 100.0% of tool-calling requests
  produced reasoning; in the three after, 99.7%. Histories that were never compacted went from 99.8% to 99.9% at the same
  call indices. Difference −0.3 points, 95% interval −1.0 to 0.0 (124 events, all matched).
- **Why:** after compaction, the next request still carried three earlier assistant turns, and in every event all three
  kept their thoughts. The history was never thought-free.
- **Reasoning length** fell by 50.8% relative to controls (95% interval −63.0% to −33.1%), but the per-call profile
  (`event_study.csv`) shows a spike just before compaction (mean 2,524 and 1,404 characters two and one calls before,
  against 808–844 in controls) and lengths at or slightly above the controls afterwards. A likely selection effect, not
  tested here: kept thoughts count toward the prompt, so long reasoning helps trigger compaction.

## Design (summary of the withheld plan)
- **Question.** E6R found that thinking fades when earlier thoughts are missing from the request history (47% of calls vs
  100%). The harness compacts long histories: when the prompt passes 14,336 tokens, older events are replaced by a
  model-written summary. Does thinking fade after that?
- **Data.** 160 task-runs (E7: 48; E8: 96; E9: 16), 4,283 completed tool-bearing requests and 207 compactions. A
  per-request ledger records history size, assistant turns and how many carry reasoning, plus the reply's reasoning
  length; a per-compaction log records start, end and error. All runs: Gemma 4 31B QAT W4A16, temperature 0.2, thinking
  budget 4,096, thoughts kept in history.
- **Unit and outcome.** A completed tool-bearing request; thinking active means non-empty reasoning text (as in E6R).
- **Event.** A run's first successful compaction, with k = 3 completed calls on each side and no other compaction attempt
  inside the window.
- **Control.** Windows at the same call index in histories that were never compacted; matched at the same index, else the
  nearest of j−1, j+1, j−2, j+2.
- **Estimate.** Difference in differences; 95% percentile cluster bootstrap over task-runs (2,000 resamples, seed 20261031).
- **Label, fixed before the run.** THINKING DROPS AFTER COMPACTION if the difference is ≤ −10 points and the interval lies
  below 0; NO MEANINGFUL DROP if the interval's lower end is above −10 points; otherwise UNCLEAR.
- **Checks before any outcome was read.** V1 record counts; V2 every compaction overlapped by a summary request; V3 the
  message count drops at every first compaction; V4 unit tests; V5 stand-in runs on the real structure with synthetic
  reasoning (null: +1.9 points, labelled no meaningful drop; planted 30-point drop: −32.8 points, labelled drop).
- **Limits.** Not randomized; compaction also shortens the context, so the estimate is the joint effect of compaction;
  settings differ from E6R (temperature 0.2 and budget 4,096 here; 1.0 and 512 there).

## Files
| File | Contents |
|---|---|
| `RESULTS.md` | Post-run record, with the reading kept separate from the label |
| `RESULTS_TABLE.md`, `results.json`, `event_study.csv`, `run_stdout.txt` | Outputs of the frozen run |
| `ct_analysis.py`, `test_ct_analysis.py`, `freeze.py`, `probe_structure.py` | Analysis code and tests (Python 3.13, standard library) |
| `validation/` | Pre-freeze outputs: structural checks, unit tests, stand-in runs |
| `FREEZE.json` | SHA-256 of every file at freeze time (2026-10-31T17:33:01Z), in the private folder layout (`audit/…`) |

Every published file from the freeze is byte-identical to its hash in `FREEZE.json`.

**Withheld** (see [DATA_AND_LICENSING.md](../../DATA_AND_LICENSING.md)): the input ledgers and compaction logs, which are
raw agent traces; `probe_stdout.txt`, which contains task identifiers (SHA-256 `f28d13a8…41ae`); and the full plan
`PLAN.md` (SHA-256 `0eed7c82…ac4d`), summarized above. All three are listed in `FREEZE.json`.
