# E7 results: strong inference-only baseline reproduction

**Status:** completed, **VALID**.

**Registered verdict:** `E7 NOT PROMISING`, unchanged. After the run, the criterion that produced this verdict was found to be flawed. The flaw is documented below as post-hoc and does not change the verdict.

## Research question

How does a publicly shared strong community configuration for Gemma 4 31B (thinking on, 4,096-token thinking budget, earlier thoughts retained), run exactly as published, perform on the fixed 48-task development panel: solves, failure modes, projected runtime for a 120-task evaluation (a planning metric, limit 12 h), and the pre-registered go/no-go rule for an external evaluation run? This is a descriptive baseline, not a causal experiment.

## Frozen configuration

- `gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4; one job at a time, 48 tasks in frozen order.
- A function-calling repository agent built on Google's Agent Development Kit: a single agent with nine tools, each task sandboxed and graded by hidden tests.
- Temperature 0.2, top_p 0.95, 8,192 max output tokens; thinking on (4,096-token budget), earlier thoughts retained.
- Per task: 28 tool calls, 8 minutes, 80 turns, 240 s command timeout.
- Preregistration frozen 2026-10-24T10:03:06Z (69 file hashes). Run time 4.19 h: vLLM start-up 339.5 s, task loop 243.3 min.

## Manipulation

None: E7 has a single arm. It differs from the earlier thinking-off runs in eight settings at once (see [PREREGISTRATION.md](PREREGISTRATION.md)), so every comparison with them is descriptive. V7 (configuration files) and V8 (settings carried by every request) confirm it ran as published.

## Validity gates

| Gate | Outcome |
|---|---|
| V1 Run status VALID; all 48 tasks ended normally | **PASS** |
| V2 48 pre-task health checks ok; 0 abort or server-exit events | **PASS** |
| V3 48 result rows, 0 problems | **PASS** |
| V4 0 model calls failed with a server error | **PASS** |
| V5 One job at a time, in the frozen order | **PASS** |
| V6 Server log persisted; host versions identical to E4 | **PASS** |
| V7 In-run check: exact published files, one arm, 48 tasks, one job at a time | **PASS** |
| V8 1,224 tool-bearing requests checked, 0 with wrong sampling or thinking fields; coverage 1.0; 0 ledger errors | **PASS** |
| X1 / X2 Evaluability: mutation log (395 records, 0 errors); trace alignment | OK / OK |

## Result

| Measure | E7 | Earlier thinking-off runs |
|---|---|---|
| Solved / 48 | **19** | 15, 15, 13 |
| CF1 Corrupted tool calls | 30/1,176 (2.5 %): ok | 6.4–10.2 % |
| CF2 Turns without a tool call | 2/1,178 (0.17 %): ok | 0.27–0.57 % |
| CF3 Tasks with a context overflow or truncation | 0: ok | 0–1 |
| CF4 New failure category | **FLAG:** `ANY:BudgetExceeded` in 9 tasks; earlier maximum 0 | – |
| Mean task wall time | 304.1 s | 135.7–145.1 s |
| Projected runtime for a 120-task evaluation | 10.64 h (**COMFORTABLE**, acceptable) | 5.02–5.34 h |

**Descriptive readouts** (registered, never part of the decision):
- **No-progress calls:** 36/1,173 (3.1 %), vs 32.4–38.5 % in the thinking-off runs; exact repeated calls 108 vs 562–747.
- **Edits and patches:** 15 tasks had no source edit; median first source edit at 190.9 s (tool-call index 12). Final-patch classes: RESOLVED 19, NO_SOURCE_PATCH 15, NO_GOLD_FILE_TOUCHED 2, PARTIAL_GOLD_FILES 6, GOLD_FILES_WRONG_FIX 6. All 35 non-empty final patches applied, with 0 compile errors.
- **Cap hits:** 8 tasks hit the 8-minute cap, 0 the turn cap. The registered call-cap readout said 0, but it was wrong (see post-hoc).
- **Thinking:** reasoning on 99.9 % of completed tool-bearing calls; reasoning tokens median 50, p90 619, max 4,094 (budget enforced); 100 % of requests kept earlier thoughts; 0 responses cut off at the length limit.
- **Context:** 60 compactions across 40 tasks; 0 context overflows.
- **Issue statements:** short, 1 of 15 solved; informative, 18 of 33.
- **Overlap:** the three thinking-off runs together solved 17 distinct tasks; E7 solved 16 of them plus 3 that none solved, and missed 1.

## Registered verdict (quoted exactly)

```
E7 NOT PROMISING  [CF4 new failure category (E3T max <= 2, E7 >= 8 tasks)]
```

The solve condition (19 ≥ 18) and the runtime condition (10.64 h, COMFORTABLE) were met, so the verdict follows from the CF4 flag alone. It stands as registered.

## Post-hoc (not registered)

Two flaws in E7's frozen analysis were found after the run, while E8 was being designed, and E8's preregistration documented both. E7's frozen report and verdict were not changed.

**1. The CF4 criterion.**
- The only category that fired CF4 was `ANY:BudgetExceeded`: the harness's refusal of tool calls after the 28-call budget is spent. That is a resource-budget outcome, not a semantic failure mode, but the frozen rule removed only `CAP:*` labels.
- No other new category came near the CF4 threshold (the largest had 4 tasks), so the registered NOT PROMISING verdict rests entirely on the resource-budget label.
- E8 excluded all resource-budget labels from CF4 and reported them in a separate table.

**2. The call-cap readout.**
- It searched each task's error text for a budget message the harness never writes. When calls run out, the agent receives refusals, usually finalizes its patch, and the task ends with an empty error, so the readout said 0.
- Rebuilt from tool replies, the correct count is **20 of 48 tasks that used all 28 calls**; 5 of the 20 were solved.
- 9 of the 20 kept requesting calls after the limit, receiving 17 refusals (9 edits, 4 reads, 4 commands); none of the 9 was solved.
- At call 28 the median capped task had used 224 s of its 480 s; only 2 of the 20 had less than 120 s left.
- All 8 time-capped tasks had used fewer than 28 calls, and none was solved.

## Limitations

- **One run is one draw.** A fresh run of the same configuration in E8 solved 21/48 vs E7's 19/48: 18 solved in both, 1 only in E7, 3 only in the fresh run.
- **Not causal:** eight settings differ from the thinking-off runs.
- **Concurrency differs:** the thinking-off runs used two concurrent jobs, so latency and runtime comparisons are approximate.
- **Small public panel:** 48 tasks from three public Python repositories, about 33 effectively informative; local solve rates are not estimates for other task sets.
- **Runtime is a local planning projection.**
- **Flawed criterion and readout:** CF4 and the call-cap readout, as described above.

## What changed because of this result

- This configuration became the CONTROL arm of E8 and the base configuration of E9.
- E8 tests the call budget directly (28 vs 36 calls), motivated by the 20 tasks that used every call.
- E8 rebuilt the call-budget metrics from tool replies (checked against E7's data) and excludes resource-budget labels from CF4.
