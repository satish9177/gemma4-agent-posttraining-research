# E5G results: research-only host-side progress guard pilot

**Status:** VALID · **LOOPS REMOVED: NO** · **BEHAVIORAL PROGRESS CREATED: NO**.
Frozen and launched 2026-10-21T16:52:28Z; completed about 2026-10-21T17:44Z (0.86 h, 20 jobs one at a time).
Preregistration summary: [PREREGISTRATION.md](PREREGISTRATION.md).

## Research question
If repeated no-progress actions are forcibly blocked, does the model turn the freed budget into earlier edits and more source
patches? An upper-bound test of deterministic progress control after the E5 prompt pilot (NO-GO).

## Frozen configuration
`gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, TP 4, 4× NVIDIA L4. Temperature 0.2, top_p 0.95, **thinking off**. 3 minutes,
50 tool calls, 150 turns, 90 s per command. The same **10 "always-looping" tasks** of the 48-task development panel as the
E5 pilot, paired, alternating arm order.

## Manipulation
Same agent in both arms. **SHADOW** logs what the guard would block but executes everything; **GUARD** withholds a call
once an equivalent call has produced an identical result three times without any intervening state change, returning the
earlier result plus a fixed notice. Blocked calls cost the same budget as real ones.

## Validity gates
All passed: V1–V8 (run status, 20 pre-task health checks and 210 in total with 0 failed, normal task ends, no server
failure, order rule, logs and host versions, mutation log, trace alignment) and GV1–GV9 (guard log complete, live = offline
metric, every block justified, blocked calls never reached the tool, budget accounting, model-visible content, no extra model
calls, deterministic replay, overhead p95 8.8 ms ≤ 50 ms). Experiment status: VALID.

## Result
| | SHADOW | GUARD |
|---|---|---|
| attempted repeats (executed NNI + blocked) / calls | 188 / 436 = 43.1 % | **183 / 451 = 40.6 %** (threshold ≤ 29.5 %) |
| near repeats | 50 | 37 (flag needed an increase ≥ max(10, 0.25 × 5) = 10) |
| tasks with no source edit | 5 | 5 (needed ≤ 3) |
| tasks with a final source patch | 5 | 5 (needed ≥ 7) |
| matched-window share of novel observations + source edits | | 3.2 % (5 + 1 of 189; needed ≥ 25 %) |

## Registered labels
As printed by the frozen report:
```
EXPERIMENT STATUS: VALID
LOOPS REMOVED: NO
EVASION FLAG: NO
LOOP ELIMINATION SUCCESSFUL: NO
BEHAVIORAL PROGRESS CREATED: NO
```

## Post-hoc (not registered)
Descriptive only; none of this changes a label.
- **Blocking worked mechanically but freed almost no budget.** Executed repeats fell 188 → 32, but GUARD logged 151 blocked
  attempts (112 consumed a tool call; 39 were free patch-submit or missing-parameter repeats). About 317 s of model time
  went to blocked attempts.
- **Persistence:** the guard blocked 10 chains; in 9 the model re-sent the identical call after the first block. Further
  attempts per chain: 0, 2, 4, 6, 9, 9, 9, 29, 36, 37 (median 9). In one task an identical probe was blocked 38 times in a
  row (37 re-sends after the first block); in another, a probe was blocked 37 times and the task ended with no source edit,
  while the SHADOW run of that task did edit. In a third, the patch-submit tool was blocked 30 times; because blocked submits
  cost no tool call, that run used 79 model turns vs 50 under SHADOW.
- **Window composition:** SHADOW 67 % executed repeats, 16 % novel observations, 2 % edits; GUARD 80 % blocked attempts, 3 %
  novel observations, 1 % edits.
- **Other counts (SHADOW / GUARD):** novel observations 159 / 158; successful source edits 8 / 6; empty final patches 4 / 4;
  median first source edit 159 s / 165 s; 3-minute timeouts 2 / 1; all 6 / 6 non-empty patches applied and compiled.
- **Failure categories:** no new failure mode flagged; four categories appeared only under GUARD, each in one task.
- **Solves (descriptive only):** SHADOW 1 / 10, GUARD 0 / 10.

## Limitations
- 10 tasks, one run per arm; tasks were selected for looping.
- SHADOW's 43.1 % is below the historical 59.1 % on the same tasks, possibly run-to-run variation or the one-job-at-a-time
  latency. The paired comparison is unaffected.
- One model and checkpoint, **thinking off**, temperature 0.2, 3-minute budget. The notice wording was fixed; no other
  wording was tested.

## What changed because of this result
- As registered, the work stopped after the pilot: no 48-task guard run.
- The interpretation recorded at the time (not a registered label) was that in-context signals, including hard blocks, do
  not steer this model's repetition and that only weight-level changes remained. **That broad conclusion was later
  superseded:** E5 and E5G both ran with thinking **off** on the 10 always-looping tasks, and the later thinking-on runs
  (E7, E8) had no-progress call rates of about 2–7 % on the 48-task panel, against 32–39 % for the thinking-off runs. Those
  runs also changed budgets, prompt and agent design, so the drop is not attributable to thinking alone. E5G is evidence
  about the thinking-off configuration only.
- Next steps at the time were a decoding-temperature experiment (E6A, frozen but never run) and a thinking-history pilot
  (E6R).
