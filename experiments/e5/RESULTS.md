# E5 results: progress-rules prompt pilot

**Status:** pilot VALID · registered decision **NO-GO** · the full 48-task paired run was not launched.
Frozen 2026-10-21T14:58:32Z; pilot completed about 2026-10-21T15:22Z (0.36 h). Preregistration summary:
[PREREGISTRATION.md](PREREGISTRATION.md).

## Research question
Do explicit progress / anti-loop rules in the system prompt cut no-new-information (NNI) tool calls enough to justify a full
paired run? NNI call = a call whose most recent identical (normalised) call by the same agent returned the same normalised
result, with no state change or context compaction in between (full definition in the preregistration).

## Frozen configuration
`gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, TP 4, 4× NVIDIA L4. Temperature 0.2, top_p 0.95, **thinking off**. 3 minutes,
50 tool calls, 150 turns, 90 s per command. Single arm (TREATMENT) on the **10 "always-looping" tasks** of the fixed 48-task
development panel: every task with ≥ 5 root-agent NNI calls in each of 3 earlier valid runs of the unchanged agent.
2 jobs at a time.

## Manipulation
A short "Progress Rules" section appended to the system prompt (paraphrased in the preregistration); nothing else changed.

## Validity gates
| Gate | Outcome |
|---|---|
| PV1 run status VALID | PASS (10/10 tasks ended normally; 71 health checks, 0 failed) |
| PV2 host versions identical to the E4 run | PASS |
| PV3 one result row, ≥ 1 model call and a trace per task | PASS |
| PV4 trace / tool-log alignment | PASS |
| PV5 mutation log present, hook errors ≤ 1 % | PASS (159 records, 0 hook errors) |

## Result
| | NNI calls / calls | NNI rate |
|---|---|---|
| Pilot (progress rules) | 191 / 445 | **42.9 %** |
| Baseline, same 10 tasks, 3 runs pooled | 806 / 1,363 | 59.1 % (58.6 / 57.3 / 61.5 %) |
| Registered GO threshold | | ≤ 29.5 % |

Ratio to baseline: 0.73.

## Registered decision
> PILOT DECISION (pre-registered): NO-GO  -> STOP: do not run the full E5.

The full paired E5 was not run, and the prompt was not tuned from these results.

## Post-hoc (not registered)
Descriptive comparisons with the 3 baseline runs on the same 10 tasks; none of them changes the decision.
- **NNI by type (pilot vs baseline mean):** check/reproduction scripts 89 vs 144 (−38 %); searches 63 vs 65; reads 30 vs 31;
  failed or no-op edits 7 vs 15. Time spent on NNI calls: 514 s vs 706 s (−27 %).
- **Loop episodes** (≥ 3 consecutive NNI calls): 10 vs 16 / 11 / 11; 159 calls inside episodes vs a mean of 246; 9 of 10
  started before any source edit.
- **Rule adoption:** resend rate 0.47 vs 0.58–0.63; a third identical check run was avoided in 5 of 10 cases; repeated
  empty searches were avoided in 23 of 84 cases (27 %, baseline pooled 28 %), so the search rule was effectively ignored;
  re-reading before retrying a twice-failed edit: 0 of 6.
- **Persisting loops:** in one task an identical one-line probe was repeated 41 times and no edit was ever made; in another,
  one search pipeline was repeated 34 times. Several remaining loops were repeated calls with corrupted argument names,
  which a prompt rule cannot recognise as "the same call". One task fell to 6 NNI calls (baseline 59 / 47 / 39).
- **Failure categories:** no new failure mode under the descriptive flag (pilot ≥ baseline mean + 3 tasks with baseline mean
  ≤ 2).
- **Solves (descriptive only):** 1 / 10 vs 0 / 10 in each baseline run; that task had been solved before by other
  configurations.

## Limitations
- Single-arm pilot against historical runs; run-to-run noise is not controlled within the pilot.
- The 10 tasks were selected *because* they looped, so regression to the mean could favour any treatment; the result still
  missed the threshold. Post-hoc (not registered): in E5G the unchanged agent (SHADOW arm, run one job at a time) reached
  188 / 436 = 43.1 % on the same tasks, about the pilot's rate, so part of the 0.73× reduction may not be due to the rules.
- One model, one checkpoint, **thinking off**, temperature 0.2, a 3-minute budget.
- The rules were tested only as prompt text; corrupted-argument repeats are outside what prompt rules can address.

## What changed because of this result
- As registered, the 48-task paired E5 was cancelled. The research-only host-side guard (E5G) was run next as an upper-bound
  test of deterministic progress control on the same 10 tasks.
- At the time, E5 and E5G together were read as evidence that the loop behaviour was intrinsic to the policy and could not
  be fixed in context. **That broad conclusion was later superseded:** both experiments ran with thinking **off** on the
  10 always-looping tasks, and the later thinking-on runs (E7, E8) had no-progress call rates of about 2–7 % on the 48-task
  panel, against 32–39 % for the thinking-off runs. Those runs also changed budgets, prompt and agent design, so the drop
  is not attributable to thinking alone. The E5 result stands only as a statement about the thinking-off configuration.
