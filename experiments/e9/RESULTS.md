# E9 results: runtime-budget pilot, 32 calls at 8 vs 7 minutes

> **Status: VALID. Registered screening decision: MIXED.** Every condition for preferring the 7-minute cap passed except
> "no new failure mode": the 7-minute arm ended with an empty final patch on 4 tasks, the 8-minute arm on none.
> No winner is declared. Solve counts (2/8 vs 3/8) are descriptive only, as preregistered.

Preregistration summary: [PREREGISTRATION.md](PREREGISTRATION.md) (frozen 2026-10-27T10:28:32Z, before any E9 output
existed; Amendment 1 was made before any output was retrieved or seen). Task identifiers are withheld; tasks are numbered
1–8 in run order, as in the preregistration table.

## Integrity of the analysis

- **Freeze check after the run:** all frozen analysis and configuration files (32) and all 10 inputs from earlier
  experiments match their SHA-256 hashes. The only file that changed after the freeze is the run-status poller's own log,
  which the poller kept appending to. It is not an input to anything.
- **The frozen report script was run unchanged** on the downloaded outputs. It was re-run on a copy of the outputs during
  this publication pass, and its printed report and all four output tables were byte-identical to the first run.
- The registered decision below is copied from that output. Everything after the "Registered labels" section is
  descriptive or post-hoc and is labelled as such.

## Run facts

| Item | Value |
|---|---|
| Launched / complete | 10:24:38Z / first check showing completion 12:06:39Z, 27 Oct 2026 |
| Run time | 1.64 h: setup 0.12 h (including a 336 s model-server start), task loop 1.52 h; expected 2.0–2.2 h |
| Deadline valve (130 min of task loop) | Not reached; the loop ended after about 91 minutes |
| Software | Same versions as E8 (vLLM 0.19.1 and the same client libraries), recorded in the run |
| Throughput check | Decode about 38–40 tokens/s; long-prompt time to first token about 1.6–1.7 s |
| Jobs | 16 of 16 ran once and ended normally; 8 of 8 complete pairs |

## Validity

| Gate | Outcome |
|---|---|
| V1 run status VALID | PASS |
| V2 16 pre-task health checks ok; no abort or server exit | PASS (394 health checks, 0 failed) |
| V3 all 16 jobs executed normally | PASS |
| V4 no model-server failure in any model call | PASS |
| V5 one job at a time, planned alternating order | PASS |
| V6 in-run bundle check: 32/8 vs 32/7, panel, one job at a time | PASS |
| V7 request path in both arms: temperature 0.2, top_p 0.95, 8,192 tokens, thinking budget 4,096 | PASS (508 of 508 requests) |
| V8 32-call budget enforced and announced in both arms; call counts reconstruct | PASS |

**E9 RUN STATUS: VALID.**

## Registered decision (preregistration section 7)

| Condition for PREFER 32/7 | Value | Pass |
|---|---|---|
| LOSS7 = 0 (A solved, B not, B reached the time cap, A's decisive edit after 420 s) | 0 | yes |
| late_B ≥ late_A − 1 (solves whose decisive edit came at budget call ≥ 28) | A 0, B 0 | yes (trivially: no late-call solve in either arm) |
| R ≥ 5 % (panel wall-time reduction) | 2,874 s → 2,572 s, R = 10.5 % | yes |
| No new failure mode in B | (i) **flagged**: empty final patch on 4 B tasks and 0 A tasks; (ii) corrupted calls B 0.4 % vs A 5.2 %: ok; (iii) B turns without a tool call 0 %: ok; (iv) no abnormal B ending: ok | **no** |
| NEC8 = 0 (A solved with a decisive edit at call ≥ 28 and after 420 s, and B did not solve) | 0 | yes |

| Condition for PREFER 32/8 | Value | Pass |
|---|---|---|
| LOSS7 ≥ 2 | 0 | no |

## Registered labels

```
E9 RUN STATUS:                    VALID (8 / 8 complete pairs)
E9 SCREENING DECISION (registered): MIXED   [failed condition: no new failure mode]
```

## Paired results (descriptive)

| # | Group | A solved | A wall s | A calls | A ending | A last source edit | A final patch | B solved | B wall s | B calls | B ending | B last source edit | B final patch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | G1 | no | 485 | 32 | time cap | none | no source change | no | 421 | 32 | time cap | none | empty |
| 2 | G1 | no | 241 | 32 | call cap | call 32 at 183 s | partial, gold files | no | 153 | 32 | call cap | none | empty |
| 3 | G1 | **yes** | 241 | 32 | call cap | call 26 at 213 s | resolved | **yes** | 368 | 32 | call cap | call 27 at 274 s | resolved |
| 4 | G2 | no | 442 | 32 | call cap | none | no source change | no | 424 | 28 | time cap | none | empty |
| 5 | G2 | **yes** | 299 | 18 | submitted | call 5 at 163 s | resolved | **yes** | 177 | 15 | submitted | call 13 at 160 s | resolved |
| 6 | G3 | no | 485 | 12 | time cap | none | no source change | **yes** | 193 | 27 | submitted | call 21 at 133 s | resolved |
| 7 | G3 | no | 344 | 32 | call cap | call 32 at 324 s | partial, gold files | no | 414 | 32 | call cap | call 14 at 223 s | partial, gold files |
| 8 | G3 | no | 337 | 32 | call cap | call 31 at 272 s | wrong fix, gold files | no | 422 | 30 | time cap | none | empty |

| Panel (8 tasks) | A: 32 calls / 8 min | B: 32 calls / 7 min |
|---|---|---|
| Solves (not a criterion) | 2 | 3 (tasks solved by both: 2; by B only: 1; by A only: 0) |
| Wall time: total / mean / median / max (s) | 2,874 / 359 / 341 / 485 | 2,572 / 321 / 391 / 424 |
| Model-generation time, total (s) | 2,820 | 2,536 ¹ |
| Tool-execution time, total (s) | 11 | 243 ¹ |
| Time-cap hits (error text / silent) | 2 (2 / 0) | 3 (3 / 0) |
| Call-cap hits | 6 | 4 |
| Empty final patch | 0 | 4 |
| Gold-file edits after budget call 28 | 3 | 0 |
| Useful action after minute 7 / solves needing it | 0 / 0 | 0 / 0 |
| Corrupted tool calls | 13 / 251 (5.2 %; 12 of them in one job, task 8) | 1 / 241 (0.4 %) |
| Turns without a tool call | 1 / 252 | 0 / 241 |
| Model-call latency, median / p90 (s) | 3.6 / 20.1 | 3.1 / 17.5 |

¹ In B, task 8 ran one shell command for 235 s until its timeout. The model-call timer for that turn overlaps it, so model
and tool seconds are not additive for that job.

## Post-hoc (not registered)

**Did minute 7 cut off anything useful? No evidence that it did.**
- In A, the only actions after 420 s were writes of reproduction scripts, not source files (tasks 1 and 4). Neither
  task was solved and neither touched a gold file.
- Useful action after minute 7 and solves needing it were 0 in both arms, so LOSS7 = 0 and NEC8 = 0.

**Is the late-call region (calls 28–32) limited by time? Not in this pilot.**
- A's three gold-file edits at budget calls ≥ 28 came at 153–324 s, well before minute 7.
- B had none. Of those three B runs, two ended on the call cap, not the time cap: task 2 submitted an empty patch at 144 s
  and used its last calls by 153 s; task 7 made its last source edit at call 14. Only task 8 was stopped by the time cap,
  after a 235-second blocking command, and A's late edits on that task were a wrong fix.
- So the 3-vs-0 difference is mostly not caused by the shorter cap, and it involved no solve.

**None of the three E8 late fixes (G1) reproduced at 32 calls in either arm.** Task 1: no source edit in either arm.
Task 2: A edited the gold files at calls 27, 28 and 32 (142–183 s) and ended with a partial fix; B submitted an empty patch.
Task 3: both arms solved it, earlier than in E8 (calls 26 and 27). The pilot therefore says nothing direct about whether a
7-minute cap keeps the E8 late fixes; it shows only that, when the late-call region was reached, it was reached before
minute 6, in E8 and in E9.

**The flagged failure mode.** All four empty final patches in B are on tasks A did not solve either: on two (tasks 1 and 4)
A's final patch was only a reproduction script written after minute 7; on task 8 A made a wrong fix; on task 2 B submitted an
empty patch itself at 144 s, far from either limit. An empty patch and a script-only patch both score zero, so the empty
patches cost no solve here. A shorter cap does mean more runs end with nothing written, so the empty-patch rate should be
tracked in any larger run.

**Runtime.** The 7-minute cap bounded the tail (maximum wall 485 → 424 s, and it cut off the 235-second command), but most
of the 10.5 % panel saving is run-to-run variation, not the cap: task 6 alone contributes −291 s because B took a different,
faster path. The saving that comes from the cap itself is at most about 60 s per job that would otherwise run past 7 minutes.
- *Preregistered descriptive projection:* E8 share of runs with wall ≥ 420 s (31.2 %) × mean paired saving on A's
  time-capped tasks (177.6 s) × 120 tasks ≈ 1.85 h saved. This **overstates** the cap effect, because 291 s of that mean
  comes from task 6's different path.
- *Post-hoc what-if on E8's 48-task wall times* (each wall clipped to the cap + 5 s; same paths assumed, so solves lost to
  an earlier cap are not modelled; P = 0.5 h + 120 × mean wall, as defined in the preregistration):

| Cap | Projection from E8's 28-call arm | Projection from E8's 36-call arm | E8 solves whose last source edit came after the cap (28-call / 36-call arm) |
|---|---|---|---|
| 8 min (as run in E8) | 10.84 h | 10.82 h | 0 / 0 |
| 7 min | 10.32 h | 10.30 h | 1 / 1 |
| 6.5 min | 9.97 h | 10.01 h | 1 / 2 |
| 6 min | 9.61 h | 9.65 h | 2 / 2 |

The 36-call configuration that exceeded the external runtime budget twice had a local projection of about 10.8 h, so a
7-minute cap alone (about 10.3 h) is not a reliable margin against the 9.5–10.0 h target set after those overruns.

## Limitations

- 8 stress-selected tasks, one run per arm, temperature 0.2. Per-task differences are mostly sampling noise, and the
  2-vs-3 solve count means nothing.
- The panel was chosen to stress late calls and long runs, so its mean wall time (about 340 s) does not represent the
  48-task panel or a larger task set.
- No E8 late fix reproduced, so the "late_B ≥ late_A − 1" condition passed trivially (0 vs 0).
- The system prompt still states 28 tool calls and 8 minutes in both arms (a known, preregistered caveat); the harness
  announced the real 32-call budget in tool replies.
- The runtime what-if is post-hoc and assumes that paths would not change under a shorter cap.

## What changed because of this result

- **Registered:** MIXED. No configuration is preferred by the registered rule. E8 is unchanged.
- **Judgement, not registered:** 8-minute caps are ruled out on runtime grounds, since on E8's data they project to about
  10.8 h, the same as the configuration that overran twice. If the runtime question is pursued, the next step would be a
  new, separately preregistered paired 48-task comparison of 7- versus 6-minute caps at 32 calls. Nothing has been
  preregistered or run.
- **For the planned post-training study:** nothing changes. Its scaffold already uses call and token budgets with no
  wall-clock cap ([RESEARCH_PLAN.md](../../RESEARCH_PLAN.md) §4.1). E9 is consistent with that choice, because the late-call
  behaviour depended on the call budget rather than the clock, but an 8-task pilot cannot establish it.
