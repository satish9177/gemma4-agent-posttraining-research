# E8 results: paired tool-call budget, 28 vs 36 calls

**Status:** completed, **VALID**. Registered verdicts: competitive `E8 WIN`; mechanism `BUDGET BOTTLENECK NOT CONFIRMED (M2 held, M1 failed)`.

## Research question

Does raising the binding tool-call budget from 28 to 36 calls let the E7 agent turn more reasoning into successful patches, without pushing the projected runtime for a 120-task evaluation (a planning metric) past 12 h? The question came from E7, where 20 of 48 tasks used all 28 calls.

## Frozen configuration

- **Timeline:** preregistration frozen 2026-10-24T18:08:41Z with 60 file hashes; launched 2026-10-24T18:10:51Z; the run took 8.41 h (task loop 495.9 min).
- **Both arms:** the E7 configuration byte for byte, except `max_tool_calls`. Model `gemma-4-31b-it` (QAT W4A16) on one vLLM 0.19.1 server (tensor parallelism 4, 4× NVIDIA L4); temperature 0.2, top_p 0.95, 8,192 max output tokens, thinking on with a 4,096-token budget, thoughts retained; 8 minutes, 80 turns and a 240-second command timeout per task; nine tools, a single agent, no adapters.
- **Run shape:** one job at a time on the fixed 48-task panel, arms alternating per task.
- **Pre-registered limitation:** the system prompt was the same in both arms and **still said 28 tool calls** (and 8 minutes). TREATMENT learned its real budget only from harness warnings (from call 26) and the status tool.

## Manipulation

`max_tool_calls` was 28 in CONTROL and 36 in TREATMENT. In the harness it also sets the refusal point (call 29 or 37), the start of the low-budget warning (call 18 or 26) and the budget the status tool reports; all three are part of the treatment. The in-run manipulation check **V9 passed**: CONTROL used at most 28 counted calls and was only ever told 28; TREATMENT used at most 36 and was only told 36.

## Validity gates

| Gate | Outcome |
|---|---|
| V1 Run status VALID; 96/96 jobs ended normally | **PASS** |
| V2 96 pre-task health checks ok; 0 abort or server-exit events | **PASS** |
| V3 96 result rows, 0 problems | **PASS** |
| V4 0 model calls failed with a server error | **PASS** |
| V5 One job at a time, in the planned alternating order | **PASS** |
| V6 Server log persisted; host versions identical to E4 | **PASS** |
| V7 In-run bundle check: exact bundles, budgets 28 / 36, 48 tasks, one job at a time | **PASS** |
| V8 Request path: 1,251 + 1,332 tool-bearing requests checked, 0 bad; coverage 1.0; 0 ledger errors | **PASS** |
| V9 Budgets enforced and announced: CONTROL 28, TREATMENT 36 | **PASS** |
| X1–X3 Evaluability, both arms (call counts rebuilt consistently for 48/48 tasks) | all OK |

## Result

| Measure | CONTROL (28) | TREATMENT (36) |
|---|---|---|
| **Solved / 48: 21 → 24, paired Δ +3, exact McNemar p ≈ 0.25 (descriptive)** | **21** | **24** |
| Paired outcome: both / control-only / treatment-only / neither | 21 / 0 / 3 / 24 | |
| Reached own call limit (n) | 16 | 11 |
| Ended at any resource cap (a) | 24 | 19 |
| Time-cap hits / turn-cap hits | 10 / 1 | 9 / 0 |
| Tasks with calls refused after the limit / refusals | 11 / 20 | 8 / 11 |
| Solved / unsolved while at the call limit | 2 / 14 | 4 / 7 |
| Source edits after budget call 28 (tasks) | 0 | 12 (7) |
| U: final patch changed after call 28 and touches a gold file | 0 | 7 |
| D: solves with the decisive edit after call 28 | 0 | 3 |
| Corrupted tool calls | 27/1,204 (2.2 %) | 20/1,281 (1.6 %) |
| Turns without a tool call | 0.25 % | 0.31 % |
| No-progress calls | 7.1 % | 2.2 % |
| Context overflows / truncated responses | 0 / 0 | 0 / 0 |
| Mean task wall time | 310.2 s | 309.6 s |
| Projected runtime for a 120-task evaluation | 10.84 h | 10.82 h (COMFORTABLE) |

**Descriptive readouts** (registered):
- **Tasks where CONTROL used all 28 calls (16):** in TREATMENT, 9 reached 36 calls, 1 ended at 29–35 and 6 at 28 or fewer; 1 was time-capped. CONTROL solved 2 of them, TREATMENT 4.
- **Arm position:** CONTROL solved 9/24 when it ran first and 12/24 when second; TREATMENT 13/24 first and 11/24 second.
- **Patch check:** 37/37 (CONTROL) and 40/40 (TREATMENT) non-empty final patches applied, with 1 compile error in each arm.
- **Thinking:** reasoning present on 99.8 % (CONTROL) and 99.6 % (TREATMENT) of tool-bearing calls; budget enforced (maximum 4,094 tokens); earlier thoughts retained on 100 % of requests.
- **Reproducibility:** the same configuration solved 19/48 in E7 and 21/48 as the fresh CONTROL; 18 tasks were solved in both runs, 1 only in E7 and 3 only in CONTROL.

**The three treatment-only solves**, numbered as in the E9 panel (group G1), without task identifiers:

| | CONTROL run | TREATMENT run |
|---|---|---|
| G1-1 | 22 calls; ended at the 8-min time cap (482 s); no source patch | 33 calls; decisive edit at budget call **30**; solved; 365 s |
| G1-2 | 28 calls (limit); ended at the time cap (485 s); patch touched only some gold files | 36 calls (limit); decisive edit at budget call **31**; solved; 313 s |
| G1-3 | 28 calls (limit); ended at the time cap (484 s); patch touched no gold file | 36 calls (limit); decisive edit at budget call **28**; solved; 299 s |

## Registered verdicts (quoted exactly)

```
E8 COMPETITIVE VERDICT (pre-registered): E8 WIN
E8 MECHANISM VERDICT (pre-registered): BUDGET BOTTLENECK NOT CONFIRMED (M2 held, M1 failed)
```

- **Competitive:** 21 → 24 solves, Δ = +3 (exact McNemar p ≈ 0.25, descriptive), meets the Δ ≥ +3 threshold exactly. No catastrophic non-budget failure fired (CF1 corrupted calls 1.6 %; CF2 turns without a tool call 0.31 %; CF3 0 tasks; CF4 no new semantic category). Projected TREATMENT runtime was 10.82 h, within 12.0 h.
- **Mechanism:** **M1 failed.** It needed a drop of at least 6 in call-limit endings; the drop was 16 → 11, i.e. 5. The other two M1 terms held (11 ≤ 0.70 × 16; any-cap endings fell 24 → 19). **M2 held:** U = 7 (≥ 5) and D = 3 (≥ 2).

## Post-hoc (not registered)

- **The gain is within single-run noise.** The 21 → 24 gain (exact McNemar p ≈ 0.25) sits exactly at the WIN threshold and is close to the difference between two runs of the *same* configuration (19 vs 21, 4 tasks discordant).
- **The time cap mattered in CONTROL.** In all three treatment-only tasks the CONTROL run ended at the 8-minute time cap, while the TREATMENT run finished in 299–365 s. In G1-1, CONTROL used only 22 calls and never reached its call limit, so that discordance is not explained by the 28-call cap.
- **Which solves count toward D.** Two treatment-only solves had their decisive edit after call 28 (calls 30 and 31); the third had it at call 28, within CONTROL's budget. D = 3 is those two plus one task that both arms solved.
- **Runtime did not change.** A recalculation from the raw traces gives a paired runtime difference (TREATMENT − CONTROL) of −0.7 s per task, with an approximate 95 % interval of −34 to +33 s.
- **Silent time caps.** A later check (E9 Amendment 1) found two solved E8 runs, one per arm, that used the full 480 s of agent time without a time-cap message. They are not in the registered time-cap counts (10 / 9), which stand.

## Limitations

- **Single paired run.** With 3 discordant tasks, all in one direction, the run cannot separate a small effect from noise. The McNemar p is descriptive and was not a registered test.
- **Prompt not updated** (pre-registered). The prompt said 28 calls in both arms, so this is not a test of a prompt-aware 36-call agent.
- **Bundled treatment.** The cap, the warning timing and the status report change together.
- **Small, public panel.** 48 tasks from three public Python repositories. The 15 tasks with short issue statements were rarely solved (1 and 2 solves), so about 33 tasks are effectively informative. Local solve rates and runtimes may not transfer to other task sets.
- **Time-capped tasks.** 9–10 tasks per arm hit the 8-minute time cap, and extra calls cannot help them.

## What changed because of this result

- The mechanism result does not support "the 28-call cap is the main bottleneck". The competitive result is a narrow, single-run gain at the minimum threshold.
- Runtime became an explicit design target: E9 tests 32 calls with an 8-minute vs a 7-minute cap. A projected 10.8 h against a 12 h limit is no longer treated as a safe margin.
- A variant whose prompt states 36 calls was noted in the preregistration but not built.

## Operational follow-up (external runtime)

An external evaluation of the 36-call / 8-minute configuration on a larger, different task set exceeded its aggregate runtime budget twice, in byte-identical runs on different days. Per a pre-specified rule there was no third attempt, and the configuration was classified operationally unsafe. No performance conclusion is drawn from these runs. This motivated explicit runtime-safety experiments ([E9](../e9/PREREGISTRATION.md)). The registered E8 verdicts above are unchanged.
