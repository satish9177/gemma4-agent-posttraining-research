# E5 preregistration (public summary): progress / anti-loop prompt rules

> **Provenance.** Sanitized public summary written 2026-10-27, after the run. The frozen original is withheld because it
> contains restricted benchmark task identifiers and evaluation-platform details. SHA-256 of the original file and its UTC
> freeze time are listed so it can be verified if released.
>
> - Original file SHA-256: `b1a5b0d5f0a3e477a534c1c748a36ad23ef786f99d406d0704bd34c05b87c58d`
> - Frozen: **2026-10-21T14:58:32Z** (UTC, from the original's freeze footer). The pilot was launched 17 s later.
> - The original's footer also lists SHA-256 values of the other frozen files (agent configurations for both arms, the
>   prompt addition, metric and report code, baseline numbers, task list, validation outputs). Those files are withheld.

## 1. Question
Can explicit progress / anti-loop rules in the system prompt convert more of the fixed per-task budget into useful work?

Background stated in the preregistration: in the 3 valid earlier runs of the unchanged agent on the fixed 48-task
development panel, 35.3 % of tool calls (1,641 / 4,651) gave no new information, costing 26.6 % of agent time.

## 2. Design
Two stages, both frozen before anything ran:
1. **Go / no-go pilot** (single arm, TREATMENT only) on the 10 "always-looping" panel tasks, compared with a historical
   baseline on the same tasks. The pilot is never part of the E5 verdict.
2. **Full paired E5** on all 48 panel tasks, CONTROL vs TREATMENT, to be run **only after GO**, unchanged.

## 3. Arms
- **CONTROL:** the frozen E3 treatment agent configuration (byte-identical to the E4 control).
- **TREATMENT:** CONTROL with a short "Progress Rules" section (about 1 KB) appended to the end of the system prompt. This is
  the only change: the old system prompt is a strict byte prefix of the new one, and every other file is byte-identical.
  In paraphrase, the section states that re-issuing an unchanged file read, search or check whose output has not changed
  spends budget without new information, and gives five rules:
  - review the call history and skip any call already made while the files are unchanged;
  - stop rerunning a check script once it has repeated an identical outcome; instead reason about the cause, look at the
    code most likely involved, and either change it or switch to a clearly different diagnostic;
  - do not repeat a search that came back empty or unchanged; try another name or open the probable file;
  - if one edit has failed twice, view the target lines afresh before another attempt;
  - use the patch-submit tool only once source code has been modified, and never on two consecutive calls; an empty
    patch means nothing has been fixed yet.

**Why prompt-only:** the agent-configuration format used by the evaluation harness cannot attach tool-call callbacks, so a
deterministic tool-call guard cannot be part of a deployable agent. A research-only host-side guard was excluded from E5
and tested separately (E5G).

## 4. Held fixed (identical to the valid E3 and E4 runs)
- Model `gemma-4-31b-it` (QAT W4A16 checkpoint), no adapters; vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4.
- Temperature 0.2, top_p 0.95, max output tokens 8,192, **thinking off** (thinking budget 0), no per-request seed.
- Budgets: 90 s per command, 50 tool calls, 3 minutes, 150 turns per task.
- Harness and library versions, sandbox image, test dependencies and server configuration identical to the reference runs.
- One vLLM server; arms alternate order per task; 2 jobs at a time; health checks before and after every task plus a 15 s
  watchdog; any server failure or abnormal task end aborts the run as INVALID.
- Read-only instrumentation identical in both arms; it never changes tool arguments or results and uses no tool budget.

## 5. Definitions
- **No-new-information (NNI) call:** a call (the status-check tool excluded) whose most recent earlier call by the same
  agent had the same *normalised* signature and returned the same *normalised* result, with no state change strictly between
  them and no context compaction between the earlier result and the new call.
- Normalisation removes cosmetic differences (working-directory prefixes, redirections, whitespace, quoting of simple
  commands; durations, addresses, temp paths, sandbox ids and clock times in results).
- **State change:** a successful edit or write; a command that writes files; a temp-file write or removal; or any call after
  which the logged workspace fingerprint changed.
- **NNI rate** = NNI calls / all calls except status checks (root agent + analysis sub-agent), pooled over tasks.

## 6. Pilot (go / no-go)
- **Tasks:** every panel task with ≥ 5 root-agent NNI calls in each of the 3 valid baseline runs: 10 tasks, frozen order.
- **Baseline** on those tasks: **806 / 1,363 = 59.1 %** (per run 58.6 %, 57.3 %, 61.5 %).
- **Validity (all must pass):** PV1 run status VALID; PV2 host versions identical to the E4 run; PV3 one result row per task
  with ≥ 1 model call and a trace; PV4 trace / tool-log alignment; PV5 mutation log present with hook errors ≤ 1 %.
- **Decision rule:**
  - **GO** iff the pilot is valid and pooled pilot NNI calls / pilot calls **≤ 0.295** (exact fraction, no rounding) →
    launch the full paired E5 unchanged.
  - **NO-GO** (rate > 0.295) → stop and report; do not run the full E5.
  - **Pilot INVALID** → not evaluable; stop and report.
- Descriptive only: NNI by category, loop episodes, per-rule adoption counters, failure categories, time, caps, edits,
  solves. The prompt is never tuned from pilot traces or solves.

## 7. Full paired E5 (registered; run only after GO)
- Validity V1–V8 (run status, health, normal task ends, no server failure, order rule, logs and host versions, mutation log,
  trace alignment). A V1–V6 failure → INVALID, no verdict. If V7 or V8 fails, cond2 and cond3 are not evaluable: a +3
  result becomes INCONCLUSIVE (never WIN) and the mechanism verdict is NOT EVALUABLE.
- **Primary verdict**, diff = TREATMENT solved − CONTROL solved on 48 paired tasks:

| Condition | Verdict |
|---|---|
| diff ≤ −3 | **E5 LOSS** |
| \|diff\| ≤ 2 | **E5 TIE** |
| diff ≥ +3, cond2 and cond3 both hold | **E5 WIN** |
| diff ≥ +3, cond2 or cond3 fails | **E5 INCONCLUSIVE** |

- **cond2:** pooled NNI rate(TREATMENT) ≤ 0.5 × pooled NNI rate(CONTROL).
- **cond3:** no failure category with CONTROL ≤ 2 affected tasks and TREATMENT ≥ CONTROL + 3.
- **Mechanism verdict** (never overrides the primary one): **ANTI-LOOP MECHANISM CONFIRMED** iff cond2 and cond3; otherwise
  **ANTI-LOOP MECHANISM NOT CONFIRMED**.
- **Limitation stated before any data:** with observed run-to-run noise, the ≥ +3 rule fires about 9 % of the time with no
  effect, and about 24 % / 41 % for a true +1 / +2 task effect.

## 8. Validation completed before the freeze
- Metric code reproduced the earlier baseline analysis on all 192 earlier task-runs; golden baseline numbers asserted;
  15/15 unit tests passed.
- The text-based state-change rule agreed with the logged workspace effect on 97.5 % of instrumented calls (1,199 / 1,230).
- Static checks: both arms compile as the harness compiles them; the only difference is the appended section.
- Report dry runs on earlier outputs: the pilot report on an earlier control run as stand-in gave 61.45 % → NO-GO; the
  full-run report on the E4 run reproduced E4's registered results (TIE; mechanism NOT CONFIRMED).
