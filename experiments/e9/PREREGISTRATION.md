# E9 preregistration (public summary): runtime-budget pilot, 32 calls at 8 vs 7 minutes

> **Provenance.** Sanitized public summary written 2026-10-27. The frozen original is withheld because it contains restricted benchmark task identifiers and evaluation-platform details. SHA-256 of the original file and its UTC freeze time are listed so it can be verified if released.
>
> | | |
> |---|---|
> | Original file SHA-256 (as amended) | `32819cb2b1e7ad355de45f0fda89edb73242074e5ecf5d1fdecad389aa8089b6` |
> | Frozen (UTC) | 2026-10-27T10:28:32Z (re-freeze after Amendment 1) |
> | Files hashed in the freeze manifest | 32, plus 10 input files from earlier experiments |
> | Initial freeze (UTC) | 2026-10-27T10:24:21Z, before launch at 10:24:38Z; preregistration SHA-256 at that freeze `e12d8c57b428ac9781230599621bdf78ef0625689e0a16b3b8303558299af9b4` |
>
> Written after the run completed, from the frozen original and without consulting the run's outputs, this summary restates the frozen design, including Amendment 1, and adds no rules. The original's SHA-256 above is the binding record. **Amendment 1 was made after launch,** while the run was in progress and before any E9 output had been retrieved or seen. *(Corrected 27 Oct 2026: an earlier version said this summary was written before the outputs were retrieved; that timing cannot be verified, so the claim was removed.)*

## 0. Scope

- **What E9 is:** a runtime-engineering screening pilot, separate from the E8 science. It is not a gate for any external evaluation and does not estimate the overall solve rate. Nothing from it is sent to an external evaluation.
- **What it does not change:** E8 stands as registered: CONTROL (28 calls) 21/48 → TREATMENT (36 calls) 24/48, exact McNemar p ≈ 0.25 (descriptive); **E8 WIN**; **BUDGET BOTTLENECK NOT CONFIRMED**. No E7 or E8 file is modified.
- **Why it exists:** an external evaluation of the 36-call / 8-minute configuration exceeded its aggregate runtime budget twice, and that configuration was classified operationally unsafe. It will not be attempted a third time.

## 1. Question

Does reducing the per-task time cap from 8 to 7 minutes, at 32 tool calls, remove substantial tail runtime **without** eliminating the useful late-call behaviour around budget calls 28–31 seen in E8?

## 2. Arms (only the time cap differs)

| | Arm A | Arm B |
|---|---|---|
| Tool-call budget | 32 | 32 |
| Per-task time cap | 8 min | 7 min |

- Both arms are the E8 CONTROL files, byte for byte, except the run-limits file: tool calls 28 → 32 in both, time cap 8 → 7 minutes in B.
- **Identical:** one agent, `gemma-4-31b-it` (QAT W4A16), nine harness tools; temperature 0.2, top_p 0.95, 8,192 output tokens, thinking on with a 4,096-token budget, thoughts retained; the system prompt; 240-second command timeout; 80 turns.
- The runner keeps its CONTROL / TREATMENT labels for A / B, so the runner code stays byte-identical to the valid E8 run.
- **Known caveat** (the prompt is deliberately unchanged): in both arms the prompt still states 28 tool calls and 8 minutes, so arm B's prompt states more time than its cap. The harness enforces and announces the real 32-call budget in tool replies. E8's 36-call arm had the same prompt text.

## 3. Panel: 8 stress tasks, deterministic rule on E8 traces

- **G1 (3 tasks):** every E8 discordant solve, i.e. the three TREATMENT-only solves (decisive edits at budget calls 30, 31 and 28).
- **G2 (2 tasks):** every E8 solve whose last source edit came after 420 s of task time; adversarial to arm B.
- **G3 (3 tasks):** fill to 8 by stress score S = (E8 arms with wall ≥ 450 s) + (E8 arms with ≥ 28 tool calls), range 0–4; ties broken by total model-generation time, then total calls, then task identifier. The three selected have S = 3, hit the 8-minute cap in both E8 arms and have 960 s of model-generation time each; the fourth remaining S = 3 task (873 s) lost the tie-break.

**Disclosure.** The rule was written after viewing the E8 per-task summary table, which was unavoidable because the panel was to be selected from E8 traces. No E9 data existed then. Solve status is used only for G1 and G2; G3 uses none.

| # | Group | E8 CONTROL (28 calls) | E8 TREATMENT (36 calls) |
|---|---|---|---|
| 1 | G1 | 22 calls; time-capped (482 s); unsolved | 33 calls; 365 s; solved, decisive edit at call 30 (325 s) |
| 2 | G1 | 28 calls (limit); time-capped (485 s); unsolved | 36 calls (limit); 313 s; solved, decisive edit at call 31 (247 s) |
| 3 | G1 | 28 calls (limit); time-capped (484 s); unsolved | 36 calls (limit); 299 s; solved, decisive edit at call 28 (233 s) |
| 4 | G2 | 28 calls (limit); 284 s; solved | 29 calls; 488 s; solved, last edit at call 28 (457 s) |
| 5 | G2 | 27 calls; 485 s; solved, last edit at call 26 (437 s) | 10 calls; 218 s; solved |
| 6 | G3 | 10 calls; time-capped (481 s) | 32 calls; time-capped (488 s) |
| 7 | G3 | 27 calls; time-capped (487 s) | 35 calls; time-capped (489 s) |
| 8 | G3 | 21 calls; time-capped (485 s) | 36 calls (limit); time-capped (482 s) |

6 of the 8 hit the 8-minute cap in at least one E8 arm, and the two G2 tasks ran 485–488 s while solving; 7 of 8 reached call 28 or more in at least one arm. The panel is stress-selected and does not represent the 48-task panel. Run order is as numbered; odd positions run A then B, even positions B then A.

## 4. Execution

- 4× NVIDIA L4 on the evaluation platform, private session without internet, same container image, data sources and model source as E8.
- One vLLM 0.19.1 server (tensor parallelism 4, E8's server configuration) for both arms; one job at a time, a task's second arm starting after its first ends; health checks before and after every job; 15-second watchdog.
- An in-run bundle check stops the run before any GPU work unless both arms' files match the frozen hashes, the budgets are 32 calls / 8 min and 32 calls / 7 min, all other run limits are equal, and panel and order are as above.
- **Deadline valve:** no new job starts after 130 minutes of task loop (E8 allowed 600; expected loop about 110 minutes), because the remaining GPU allowance could not be read reliably; the run then ends cleanly and keeps its outputs.

## 5. Validity

- **VALID:** run status VALID; all 16 jobs ran once and ended normally; no model-server failure; 16 pre-task health checks ok; planned order, one job at a time; bundle check ok; request path in both arms at temperature 0.2, top_p 0.95, 8,192 tokens, thinking budget 4,096 (as E8 V8); call counts never exceed 32 and the announced budget is 32 in both arms.
- **PARTIAL:** the deadline valve fired or a job aborted. Complete pairs are analysed descriptively; with fewer than 6 complete pairs the decision is **INSUFFICIENT** (no preference).
- **INFRASTRUCTURE INVALID:** the platform stopped the session (GPU allowance or session time limit) and no run-status file exists. Outputs kept; no decision.

## 6. Measurements per (arm, task)

Solve; wall time split into model generation, tool execution and other; calls (rebuilt and checked as in E8); cap hits; final-patch class; budget index and time of the last edit and last successful source edit; **useful action after minute 7** (a source edit after 420 s in a run whose final patch touches a gold file); **solve required action after minute 7** (decisive edit after 420 s); **useful action after call 28** (E8's U); corrupted calls; turns without a tool call; termination reason. Each G1 task gets a narrative: does the known late fix still occur within 32 calls, and at which call and second, in each arm?

**Time cap reached** (as amended): the session-timeout error, **or** at least one session-time refusal, **or** an agent active span of at least the cap minus 3 s (477 s for A, 417 s for B; labelled a silent time cap). Error-based and silent counts are both reported.

## 7. Decision rule (screening)

Computed on a VALID run, or a PARTIAL run with at least 6 complete pairs (flagged). Paired definitions:
- **LOSS7:** tasks solved in A and unsolved in B, where B reached the time cap **and** A's decisive source edit came after 420 s.
- **late_A / late_B:** solves whose decisive edit came at budget call ≥ 28.
- **NEC8:** tasks where A solved with a decisive edit at budget call ≥ 28 **and** after 420 s, and B did not solve.
- **R** = 1 − Σ wall(B) / Σ wall(A) over the panel; material if and only if R ≥ 5 %.
- **New failure mode in B** if any of: (i) a semantic failure category (E8 CF4 categories, resource-budget labels excluded) on ≥ 2 B tasks and 0 A tasks; (ii) B's corrupted-call rate ≥ A's + 5 percentage points; (iii) B's turns without a tool call > 5 %; (iv) a B job that did not end normally while its A job did.

| Outcome | Rule |
|---|---|
| **PREFER 32/7** | LOSS7 = 0 **and** late_B ≥ late_A − 1 **and** R ≥ 5 % **and** no new failure mode **and** NEC8 = 0 |
| **PREFER 32/8** | LOSS7 ≥ 2 (the extra minute clearly preserves solves that minute 7 cuts off) |
| **MIXED** | otherwise, every failed condition listed; no winner is forced |

Solve counts per arm are reported but are not a criterion (8 tasks, stochastic).

## 8. Runtime and projection (never a criterion)

- Expected run about 2.0–2.2 h; worst case, bounded by the valve, about 2.7 h. If the remaining GPU allowance cannot be read, the run proceeds as in E8, and a platform stop is INFRASTRUCTURE INVALID.
- The panel's mean wall time is not representative. Reported descriptively: the per-task saving on jobs where A hit the time cap, and a rough full-run estimate (E8 frequency of tasks with wall ≥ 420 s × observed mean saving × 120).
- The real projection waits for a later full 48-task run (P = 0.5 h + 120 × mean wall; target ≤ 9.5–10.0 h). "10.8 h < 12 h" is no longer accepted as safe after the two external runtime overruns.
- **Planned next, not part of this run:** the preferred 32-call candidate (or both, if MIXED and compute allows) on the full 48-task panel. Nothing goes to an external evaluation without explicit approval.

## Amendment 1 (pre-data; made after launch, before any E9 output was retrieved or seen)

- **Finding:** testing the report script on a stand-in built from the panel tasks' E8 outputs showed two E8 runs (the late-solving runs of the two G2 tasks, one per arm) that used the full 480 s of agent time but ended with an empty error and no session-time refusal. The cap fired silently, and the original definition would have missed them.
- **Change:** the wider *time cap reached* definition in section 6.
- **Effect:** LOSS7 requires that B reached the time cap, so the wider definition can only add LOSS7 cases: the rule becomes stricter against 32/7, never looser. Nothing else changed. E8's registered time-cap counts (10 / 9) stand.
- The initial freeze record was kept, and the manifest was re-made after the amendment.
