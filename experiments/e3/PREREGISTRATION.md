# E3 preregistration (public summary): Tool-protocol reliability, read serialization

> **Provenance.** Sanitized public summary written 2026-10-27, after the runs. The frozen originals are withheld because they contain restricted benchmark task identifiers and evaluation-platform details. SHA-256 of each original file and its UTC freeze time are listed so the originals can be verified if released.
>
> | Original preregistration | SHA-256 of the original file | Frozen (UTC, from the original's freeze statement) |
> |---|---|---|
> | Run 1 | `fd02002de4f356f661d7634e87ccb9c55d05a73823412dffabf0ad0e54e2a84f` | 2026-10-17T16:57:05Z |
> | Confirmation run | `494d6b361330ca3b92e8f1abc7c4608b6d9f8a9a3d28d599a692dd9ef41b925e` | 2026-10-18T07:37:42Z |
> | Final run | `dbddc9ee3a07959829182911f1ed2e3cf89a6cfda3ae914db5e74ebce7b47a71` | 2026-10-18T12:03:09Z |
>
> Each original also lists hashes of the frozen analysis scripts and of the run script, which embeds both agent configurations. Those files are withheld as well.

One design was run three times, each under its own frozen preregistration. Results: [RESULTS.md](RESULTS.md).

## Shared design (all three runs)

**Question.** With thinking off, does short tool-protocol guidance in the system prompt, chiefly reading line ranges through a shell command, reduce malformed tool calls and increase tasks resolved for `gemma-4-31b-it`?

**Arms.**
- **CONTROL:** the frozen baseline agent configuration, byte-identical to an earlier baseline run on the same panel.
- **TREATMENT:** CONTROL plus one short section appended to the system prompt; every other file is byte-identical. In paraphrase, it asks the agent to:
  1. read line ranges with a shell command that prints those lines, not with the read tool's range arguments;
  2. keep the edit tool's match string (`old_string`) to a handful of lines copied exactly from the file;
  3. after a call fails with an argument, schema or other tool error, not send the same call again, but read the target again or use another method.

**Fixed settings.**
- Model `gemma-4-31b-it`, QAT W4A16 checkpoint, no adapters; vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4.
- Temperature 0.2, top_p 0.95, at most 8,192 output tokens, thinking budget 0 (thinking off).
- Per task: 3 minutes, 50 tool calls, 150 turns, 90 s per shell command.
- A function-calling repository agent built on Google's Agent Development Kit (nine tools, a code-analysis sub-agent); each task runs in its own sandbox, graded by hidden tests. Harness versions, container, test dependencies and task data are pinned.
- The fixed 48-task development panel, same order, two tasks at a time.

**Operational definitions** (fixed before run 1 and never changed).
- *Corrupted tool call:* a traced call whose argument keys contain a double quote, a backslash, a backtick or the chat-template prefix `<|`, or whose tool reply says mandatory parameters are missing. *Corrupted-call rate* = corrupted ÷ all traced calls, pooled per arm.
- *Corruption drops substantially:* TREATMENT rate ≤ 0.5 × CONTROL rate.
- *New major failure mode:* a failure category affecting ≤ 2 CONTROL tasks and ≥ (CONTROL tasks + 3) TREATMENT tasks, counted by per-task presence. Categories: every tool error class; malformed or missing-parameter calls; failed `sed` commands; the 3-minute and 50-call caps; runaway model calls (≥ 45 s); non-cap task exceptions; context-window-exceeded errors; an empty final patch.
- `diff` = TREATMENT resolved − CONTROL resolved on the 48 paired tasks.

## Run 1 (frozen 2026-10-17T16:57:05Z)

Arms run one after the other, CONTROL first, with the inference server restarted between them. **No validity gates were registered.**

| Condition | Verdict (exact registered label) |
|---|---|
| diff ≥ +3 AND corruption drops substantially AND no new major failure mode | WIN (printed as "E3 WIN") |
| \|diff\| ≤ 2 | TIE |
| diff ≤ −3 | LOSS (printed as "E3 LOSS") |
| diff ≥ +3 but another WIN condition fails | INCONCLUSIVE (not a win) |

*Timing note:* the original records the launch about two minutes before the stated freeze time; the first model call came about nine minutes after the freeze, so no result existed when the rule was frozen.

## Confirmation run (frozen 2026-10-18T07:37:42Z)

**Purpose:** to confirm run 1, whose verdict was INCONCLUSIVE because of the edit-failure screen. Nothing was edited or rebuilt; arms still ran sequentially with a server restart.

**Rule** (exact registered labels):
- **E3 CONFIRMED:** all three hold: (1) diff ≥ +3; (2) TREATMENT corrupted-call rate ≤ 50 % of CONTROL's; (3) the edit failure category `old_string_not_found` (match string not found in the file) does **not** meet the new-major-failure-mode rule.
- **E3 NOT CONFIRMED:** \|diff\| ≤ 2.
- **E3 REJECTED:** diff ≤ −3.
- **E3 STILL INCONCLUSIVE:** diff ≥ +3, but condition 3 triggers.
- **Gap case (fixed in advance):** diff ≥ +3, condition 3 not triggered, condition 2 fails → E3 NOT CONFIRMED.
- Only `old_string_not_found` enters condition 3; any other category meeting the rule is reported but not used.

**Validity checks:** 48 paired tasks, 48 traces per arm, host package versions identical to run 1; server health was not covered. An aggregate with run 1 is secondary evidence that never changes the verdict.

*Timing note:* the original records a launch 12 s after its stated freeze time; the first model call came about 12 minutes after the freeze. This run was later ruled invalid (see results).

## Final run (frozen 2026-10-18T12:03:09Z)

**Context.** The ruling recorded on the confirmation run was "PROCEDURAL VERDICT E3 NOT CONFIRMED; EXPERIMENT STATUS INVALID / COMPROMISED". None of its results are used as a verdict.

**Unchanged:** both agent configurations (byte-identical), all settings, harness versions, container, test dependencies, task data, the 48 tasks and their order, instrumentation and analysis scripts. **Verdict rule:** the confirmation rule above, unchanged, with all its labels.

**Changed (orchestration only).** One inference server with an identical configuration serves both arms (a shared prefix cache affects speed only). Arm order alternates by task: odd-numbered tasks run CONTROL first, even-numbered tasks TREATMENT first, and a task's second arm starts only after its first finishes. Two jobs at a time; a 300-minute deadline, and reaching it with tasks not started makes the run invalid.

**Validity rules.**
1. Every (arm, task) pair has exactly one result row with no exception, an empty error or a harness budget message, at least one model call, and a trace.
2. Any model-server failure in either arm invalidates the run: connection, HTTP 5xx or timeout-class errors in any model call, server-failure text in a task result, the server process exiting, or a health check failing all 3 attempts. Strict on purpose (an HTTP 500 from a live server counts); cancellations at the 3-minute cap and context-window-exceeded errors do not count.
3. Server output is persisted; a health log records every check, every failed attempt, and host and GPU resources every 60 s.
4. Health checks before and after every task (process alive, health endpoint 200 within 10 s, up to 3 attempts 5 s apart), plus a 15 s watchdog.
5. On server unavailability, a server failure or an abnormal task end, the run aborts, no new task starts, and the status is INVALID.
6. The analysis runs checks V1–V6 first and never calls the verdict code if any fails: V1 status VALID; V2 complete health log, no abort or server exit; V3 rule 1; V4 rule 2; V5 arm order; V6 server log persisted and host versions identical to run 1.

**Reported separately, never in the verdict:** broken range-key reads, edits missing the match string, `old_string_not_found` counts, immediate identical retries after a tool error, server health events, and solves by position within a task.

**Tests before freezing.** Runner tests against a stub server (healthy run, crash between tasks, crash during a task, connection error, non-server task failure): only the healthy case was VALID, and no job started after any abort. Analysis smoke tests: run-1 data passed V3 and V4; the invalid confirmation run failed V3 on exactly its 12 outage tasks and failed V4.
