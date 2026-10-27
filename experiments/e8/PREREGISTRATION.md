# E8 preregistration (public summary): paired tool-call budget, 28 vs 36 calls

> **Provenance.** Sanitized public summary written 2026-10-27. The frozen original is withheld because it contains restricted benchmark task identifiers and evaluation-platform details. SHA-256 of the original file and its UTC freeze time are listed so it can be verified if released.
>
> | | |
> |---|---|
> | Original file SHA-256 | `aa10317500398b2da3384c424a0970ff0aa14383d74b899a7d8e77bc73870d23` |
> | Frozen (UTC) | 2026-10-24T18:08:41Z |
> | Files hashed in the original freeze manifest | 60 |
> | Independent record | The same SHA-256 for this file is listed in the E9 freeze manifest (frozen 2026-10-27T10:28:32Z). |
>
> Written after the run, this summary restates the frozen design and adds no rules. The design was approved as drafted before the freeze; no amendment was made after it.

> **PRE-REGISTERED LIMITATION: the prompt says 28 calls, but TREATMENT's harness budget is 36.** The only intervention is the harness limit `max_tool_calls` (28 → 36). By an intentional decision, the system prompt is identical in both arms and still states 28 tool calls and 8 minutes, with a 28-call plan. TREATMENT learns its real budget only from the harness's low-budget warnings (from call 26) and the status tool. **A TIE must not be read as evidence that a prompt-aware 36-call agent cannot help;** that would need its own experiment, which was not built.

## 1. Question and motivation

Does relaxing the binding tool-call budget let the E7 agent turn more reasoning into successful patches, without pushing the projected runtime for a 120-task evaluation (a planning metric) past 12 hours?

From E7's data (rebuilt as in section 3): 20/48 tasks used all 28 calls and 5 of them were solved; 9 of the 20 kept requesting calls after the limit (17 refusals, none of the 9 solved), and 7 were still editing at calls 25–28. Time was not binding for them: at call 28 the median capped task had used 224 s of 480 s, and late calls took a median of 7.1 s. E7's 8 time-capped tasks all used fewer than 28 calls; more calls cannot help them.

## 2. Design

- **CONTROL:** the exact E7 configuration, byte for byte (28-call limit).
- **TREATMENT:** the same four files with one line changed in the run-limits file, `max_tool_calls` 28 → 36. A build-time check confirms this is the only difference.
- **Identical:** prompt; `gemma-4-31b-it` (QAT W4A16); temperature 0.2, top_p 0.95, 8,192 output tokens; thinking on (4,096-token budget, thoughts retained); 8 minutes, 80 turns, 240-second command timeout; nine tools; one agent, no adapters.
- **What the knob changes in the harness** (verified in its source and a real-harness test; all part of the treatment): the hard cap (call 29 or 37 onward is refused), the start of the low-budget warning (call 18 or 26), and the budget reported by the uncounted status tool.
- **Run shape:** the same 48 tasks as E3–E7 in frozen order; paired with a fresh control (E7 is only a descriptive column); one vLLM 0.19.1 server (tensor parallelism 4, 4× NVIDIA L4), one job at a time, arms alternating per task. The runner is reused unchanged from the frozen E6R pilot (health checks around every job, 15-second watchdog, abort on any server failure). An in-run bundle check stops the run before GPU work unless both arms are exactly as specified. Reaching the 600-minute task-loop deadline makes the run INVALID, with no verdicts.

## 3. Corrected call-budget measurement

E7's "call-cap hits" readout searched for error text that the harness never writes, so it read 0 instead of 20. E7's frozen report is **not** changed; E8 uses rebuilt per-task metrics for an arm with budget B:
- **Counted calls:** tool replies that actually ran, excluding budget refusals, calls rejected before the tool ran (missing parameters), session-time refusals, and the uncounted finalize and status tools. A command timeout counts. The rebuilt count must equal the harness count (X3).
- **Reached call limit:** harness call count = B. **Attempted after limit:** at least one budget refusal. **Budget index:** the k-th counted call has index k. **Decisive edit:** the task's last source edit.
- **Verified before the freeze:** unit tests A1–A12 reproduce E7's call-cap figures (20 at the limit, 9 attempting after it, 17 refusals, 5 solved; rebuilt = harness counts on 48/48), and real-harness checks B0–B5 confirm for both arms that exactly 28 or 36 calls run, later calls are refused, and the first warning comes at call 18 or 26.
- **Resource-budget labels are not semantic failures.** CF4 excludes cap labels, budget refusals, timeout labels and turn-budget ends; they are reported in a separate table.

## 4. Validity (any failure: E8 INVALID, no verdict at all)

| Check | Rule |
|---|---|
| V1 | Run status VALID: no abort; all 96 jobs executed and ended normally |
| V2 | 96 pre-task health checks ok; no abort or server-exit event |
| V3 | Exactly one result row per (arm, task), with no exception, a normal end, at least one model call and a trace |
| V4 | No model call failed with a model-server error |
| V5 | One job at a time, in the planned alternating order |
| V6 | Server log persisted; host versions identical to E4 |
| V7 | In-run bundle check ok: arms exactly as pinned; budgets {CONTROL 28, TREATMENT 36}; other run limits equal; 48 tasks; one job at a time |
| V8 | Every tool-bearing request in both arms has temperature 0.2, top_p 0.95, 8,192 tokens, thinking on with budget 4,096; ledger coverage in [0.99, 1.01] per arm; ledger errors ≤ 1 % |
| V9 | **Manipulation check (required):** CONTROL never exceeds 28 counted calls and every budget number it is told is 28; TREATMENT never exceeds 36 and every number is 36; each arm names its own budget at least once |

- If V9 fails, the run is INVALID even when every other check passes.
- **INFRASTRUCTURE INVALID:** the compute platform stops the run before the run-status file is written (for example, GPU allowance or session time exhausted). Outputs are kept, but no verdict is computed from a partial subset and no completed tasks are selected after the fact. The same applies to any other INVALID run.
- **Evaluability** (never invalidates the run): X1 mutation log ok; X2 traces align; X3 rebuilt call counts equal harness counts on 48/48 tasks per arm. If X2 or X3 fails, the mechanism verdict is NOT EVALUABLE.

## 5. Pre-registered competitive verdict

Δ = TREATMENT solves − CONTROL solves, paired on the same 48 tasks.

| Verdict | Rule |
|---|---|
| **WIN** | Δ ≥ +3 **and** no catastrophic non-budget failure (CF1–CF4) in TREATMENT **and** projected TREATMENT runtime ≤ 12.0 h |
| **INCONCLUSIVE** | Δ ≥ +3, but a catastrophic flag or the runtime condition fails (every failure listed) |
| **TIE** | \|Δ\| ≤ 2 |
| **LOSS** | Δ ≤ −3 |

- **Catastrophic non-budget failure in TREATMENT** (E7's thresholds; CF4 baseline is the paired CONTROL): CF1 corrupted calls (E3 definition) > 15 % of traced calls; CF2 turns without a tool call > 5 %; CF3 ≥ 5 tasks with a context overflow or length-truncated response; CF4 a new **semantic** failure category (resource labels excluded) in ≥ 8 TREATMENT tasks while CONTROL has ≤ 2.
- **Runtime:** P = 0.5 h + 120 × mean TREATMENT task wall time / 3600, as in E7. Acceptable if and only if P ≤ 12.0 h; COMFORTABLE if P ≤ 11.0 h, TIGHT if 11.0 h < P ≤ 12.0 h.
- **Why ±2:** three earlier reruns of one identical configuration differed in solves by 0, 2 and 2, and each pair disagreed on 2–4 tasks, so one paired run resolves only differences of about 3 or more.

## 6. Pre-registered budget-mechanism verdict (independent of section 5)

**BUDGET BOTTLENECK CONFIRMED** if and only if **M1 and M2** both hold; otherwise NOT CONFIRMED, stating which part held. The two verdicts are computed and reported separately and neither changes the other (a WIN with the bottleneck not confirmed, or a TIE with it confirmed, are both possible).

- **M1, material reduction in call-exhaustion endings: n_C − n_T ≥ 6 and n_T ≤ 0.70 · n_C and a_C − a_T ≥ 3.** n_X = tasks that reached their own call limit; a_X = tasks that ended at any resource cap (call limit, 8-minute time cap or turn cap). 6 is one third of E7's 20 capped tasks; the any-cap term stops a shift from the call cap to the time cap from counting as relief. One run's capped count has a binomial SD of about 3.4, so this is a materiality rule, not a significance test.
- **M2, useful work after call 28 in TREATMENT: U ≥ 5 and D ≥ 2.** U = tasks whose final source patch was last changed after budget call 28 **and** touches a gold source file (final class RESOLVED, PARTIAL_GOLD_FILES or GOLD_FILES_WRONG_FIX); D = RESOLVED tasks whose decisive edit came after budget call 28. U ≥ 5 is roughly half of the about 11 E7 tasks whose work the cap cut off; D ≥ 2 because one discordant solve is within rerun noise. U and D are 0 in CONTROL by construction.

## 7. Reporting plan

Both arms side by side, with E7 as a descriptive column: solves, paired both / CONTROL-only / TREATMENT-only / neither and an **exact McNemar p (descriptive only)**; call-cap, time-cap and after-call-28 readouts; failure, context, runtime, patch and thinking readouts; arm position. Every discordant task is inspected by hand. On a stand-in that duplicates E7 into both arms, the report reproduces E7 and yields a TIE, and **V9 fails by design** because the stand-in "treatment" announces 28: the guard against a treatment that silently did not take effect.

## 8. Runtime planning (not a verdict)

From E7's per-task timings, the projected TREATMENT runtime was estimated at 10.35–11.53 h (central 10.97 h; E7 10.64 h); the high case is TIGHT, and run-to-run noise is about ±0.5 h. Expected run 8.2–8.7 h, worst case about 11 h. The experiment is not shortened to fit the available GPU allowance; a platform stop is INFRASTRUCTURE INVALID.

## 9. Not done in E8

No change to temperature, thinking budget, prompt, early-edit rules, compaction or training; no re-run of earlier configurations; no prompt-aware 36-call variant; no modification of E7, whose artifacts and registered verdict (**E7 NOT PROMISING**) are read only.
