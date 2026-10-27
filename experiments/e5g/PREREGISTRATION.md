# E5G preregistration (public summary): research-only deterministic progress guard pilot

> **Provenance.** Sanitized public summary written 2026-10-27, after the run. The frozen original is withheld because it
> contains restricted benchmark task identifiers and evaluation-platform details. SHA-256 of the original file and its UTC
> freeze time are listed so it can be verified if released.
>
> - Original file SHA-256: `12264bf7482b3820ff49368af1162906811d2898b1bbe00e2ef37a0d3c5b9d15`
> - Frozen: **2026-10-21T16:52:28Z** (UTC, from the original's freeze footer). The run was launched in the same second.
> - The original's footer also lists SHA-256 values of the other frozen files (guard code, post-run code, run builder,
>   report script, unit tests, historical replay, CPU battery outputs, agent configuration). Those files are withheld.

## 1. Question
When wasted repeated actions are forcibly removed, does the model convert the saved budget into earlier edits and more
successful patches? This is an upper-bound test of deterministic progress control, run after the E5 prompt-only pilot
(NNI 59.1 % → 42.9 %, NO-GO).

**Scope:** the guard is a research instrument in the private evaluation setup only. The agent-configuration format used by
the evaluation harness cannot attach tool callbacks, so the guard cannot be part of a deployable agent. After the pilot:
report and stop (no 48-task guard run). Warning wording and thresholds were never to change after launch.

## 2. Arms (paired: same 10 tasks, same server)
Both arms run the identical frozen E3 treatment agent with no prompt change. The only difference is the guard mode:
- **SHADOW** (runner arm CONTROL): every guard decision is computed and logged; every call executes normally.
- **GUARD** (runner arm TREATMENT): the guard enforces its blocks.

Tasks: the same 10 always-looping panel tasks as the E5 pilot, in frozen order (historical NNI on them 806 / 1,363 =
59.1 %). Instrumentation is identical in both arms.

## 3. Guard algorithm (described, not quoted)
- Uses the frozen E5 normalisation, state-change rule and NNI chain unchanged (the analysis modules are hash-checked at run
  time). The status-check tool and sub-agent invocations are never blocked.
- **Equivalence:** same agent and same normalised call signature. **Anchor:** the most recent *executed* call with that key.
- **Block rule:** block iff the anchor's chain is ≥ 3 (the original plus 2 repetitions all returned the same normalised
  result), no executed call since the anchor changed state, and no context compaction began after the anchor's result.
- **Blocked call:** the tool is not called. The model receives the anchor's earlier result unchanged plus a fixed notice.
  On the first block of a chain, the notice (paraphrased) reports that the call was skipped because an equivalent call had
  already given an identical result three times with nothing relevant changed, and asks the model to do something clearly
  different. Later blocks give a shorter notice with the block count and the previous result. There is no third level: the guard never forces an edit, ends a turn, changes
  repository state or gives task advice.
- **Budget:** a blocked call costs exactly what the real call would (one tool call; the patch-submit tool checks only time
  and costs no call, as in the harness; a repeated missing-parameter error costs nothing). The 50-call, 3-minute and
  150-turn limits are unchanged.
- **Safety:** any guard error fails open (the call executes). The guard never runs sandbox commands, writes files or calls
  a model. Every decision is logged.

## 4. Held fixed
- `gemma-4-31b-it` (QAT W4A16), no adapters; vLLM 0.19.1, TP 4, 4× NVIDIA L4.
- Temperature 0.2, top_p 0.95, 8,192 output tokens, **thinking off**.
- 90 s per command, 50 tool calls, 3 minutes, 150 turns per task.
- One vLLM server; arm order alternates per task; health checks before and after every task, 15 s watchdog; abort → INVALID.
- **One job at a time** (the historical runs used 2), so per-call latency is lower than in the baseline runs; the concurrent
  SHADOW arm is the same-condition control for every time-based measure.

## 5. Registered verdicts (GUARD arm, pooled over the 10 tasks)
- **LOOPS REMOVED** iff the attempted-repeat rate is **≤ 29.5 %**. Attempted repeats = executed NNI calls (frozen metric on
  the executed sequence) + blocked attempts; denominator = all calls except status checks (executed + blocked).
- **EVASION FLAG** iff near repeats(GUARD) − near repeats(SHADOW) **≥ max(10, 0.25 × (attempted repeats(SHADOW) −
  attempted repeats(GUARD)))**. A near repeat is an executed information call that is one of: a same-result call with a
  different signature (RNI); a close variant (same agent and category, different signature, text similarity ratio
  **≥ 0.95**, nothing changed, new non-empty result); or a re-read of content already covered.
- **LOOP ELIMINATION SUCCESSFUL** iff LOOPS REMOVED and not EVASION FLAG. A reduction accompanied by the evasion flag is
  never described as successful loop elimination.
- **BEHAVIORAL PROGRESS CREATED** iff at least 2 of 3 hold:

| Criterion | Threshold | Historical baseline (3 runs) |
|---|---|---|
| (a) tasks with no source edit | ≤ 3 | 7 / 7 / 5 |
| (b) tasks whose final patch modifies a package source file | ≥ 7 | 3 / 3 / 5 |
| (c) matched-window share of novel observations + source edits | ≥ 25 % | 2–9 % |

  The matched window runs from a task's first block (SHADOW: first would-block) to its end. Each root call in it is
  classified once, in the order blocked attempt > executed repeat > near repeat > source edit > submit > novel observation
  > other. A novel observation is an executed information call whose non-empty result is new for that agent since the
  last state change.
- **Descriptive only:** solves, patch correctness, apply/compile, blind edits, failure categories, first-edit timing,
  timeouts, exact vs near repeats, every intervention, model time on blocked attempts.

## 6. Validity (any failure → INVALID, no verdict)
- V1–V6: run status, pre-task health checks, normal task ends in both arms, no model-server failure, order rule, server log
  persisted, host versions identical to the E4 run. V7: mutation log in both arms, hook errors ≤ 1 %. V8: trace / tool-log
  alignment.
- GV1 one guard record per tool call, guard errors ≤ 1 %; GV2 live guard state equals the frozen offline metric; GV3 every
  block satisfies the rule offline; GV4 blocked calls never reached the tool or changed the workspace, and SHADOW has no
  blocks; GV5 budget spent exactly as the real call would; GV6 model-visible block content = earlier result + fixed notice;
  GV7 no extra model calls; GV8 deterministic replay; GV9 guard overhead p95 ≤ 50 ms.

## 7. Validation completed before the freeze
- 16/16 unit tests on the real guard code.
- Historical replay over 144 baseline task-runs (4,635 guarded calls): 0 mismatches with the frozen metric, 0 false blocks.
- CPU real-stack battery with a scripted, non-adapting stand-in model: v1 passed 11 of 12 gates (an offline-check gap for
  sub-agent calls that share a trace step; the offline check was fixed, the guard code was unchanged); v2 passed all 12.
- Report dry run on battery output: all checks pass; with a non-adapting model the attempted-repeat rate stays at 80.6 % and
  LOOPS REMOVED is NO, i.e. persistence is measured rather than hidden.
