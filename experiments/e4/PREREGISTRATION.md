# E4 preregistration (public summary): Tool-protocol reliability, edit protocol

> **Provenance.** Sanitized public summary written 2026-10-27, after the run. The frozen originals are withheld because they contain restricted benchmark task identifiers and evaluation-platform details. SHA-256 of each original file and its UTC freeze time are listed so they can be verified if released.
>
> | Original | SHA-256 of the original file | Frozen (UTC, from the original's freeze footer) |
> |---|---|---|
> | Preregistration v1 | `efc657b00c98f82f00e3fdef447b65bb0969bedd5a60dcb753a8580425f103c6` | 2026-10-21T08:59:44Z |
> | Amendment v2 (analysis-code fix) | `bf162b55683c7181f17d16867ab90fbf46197344f43c789c6ebc299eccc19f67` | 2026-10-21T10:12:41Z |
>
> v1 is preserved unchanged, and the amendment pins its hash. The 48-task run was launched 10 s after the amendment freeze. Each footer also lists SHA-256 values of the other frozen files (both agent configurations, the prompt addition, run, logging and analysis code, validation and pilot files). Those files are withheld.

Results: [RESULTS.md](RESULTS.md).

## 1. Question
E3's guidance fixed reads but not edits. In the E3 final run's TREATMENT arm (the E4 control), 41 of 99 edit-tool calls arrived without the match string (in 5 tasks) and 49 of 99 failed. Can edit corruption be reduced by expressing each source edit as one shell-command string, as E3 did for reads?

## 2. Arms
- **CONTROL:** the frozen E3 TREATMENT configuration, byte-identical.
- **TREATMENT:** CONTROL with a short "Safe Editing" section appended to the system prompt. This is the only change: the old prompt is a strict byte prefix of the new one, and the other five files are byte-identical. In paraphrase, it asks the agent to edit source through the shell tool with one fixed template: a small Python script in a quoted heredoc that reads the file, asserts the old text occurs exactly once, replaces it, and prints the git diff. Its rules: re-read the target lines just before editing and copy the old text from that output; keep the old text small but unique, without placeholders; keep the template's quoting; fall back to the edit tool when the text contains a triple quote or a path the harness rewrites; check the diff; after a failure, re-read and rebuild instead of resending.

## 3. Held fixed (identical to the valid E3 final run)
- Model `gemma-4-31b-it` (QAT W4A16), no adapters; vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4.
- Temperature 0.2, top_p 0.95, at most 8,192 output tokens, thinking budget 0 (thinking off), no per-request seed.
- Per task: 90 s per command, 50 tool calls, 3 minutes, 150 turns.
- Harness versions, container, test dependencies, task data, server configuration; the fixed 48-task development panel in the same order.
- Orchestration: one server for both arms, arm order alternating by task, 2 jobs at a time, health checks around every task plus a 15 s watchdog, abort as INVALID on any server failure or abnormal task end, persisted server log, 300-minute deadline.

## 4. The only other addition: read-only mutation logging (both arms)
A hook on the edit, write and patch-submit tools and on non-read shell commands records file hashes before and after, the template's pre-call match count, the working-tree diff and a syntax check of changed Python files. It never changes tool arguments or results, uses no tool budget and never writes to the workspace. Overhead threshold, set before measuring: p95 snapshot latency ≤ 150 ms; projected cost ≤ 1.8 s (median task) and ≤ 3.6 s (p95 task).

## 5. Validity
- **V1–V6:** the E3 final run's six checks, imported unchanged; V6 compares host versions with that run. Any failure → INVALID, no verdict.
- **V7:** the mutation log has records in both arms, with hook errors ≤ 1 % of each arm's records. If V7 fails the run stays valid, but cond2 cannot be evaluated, so a +3 result becomes E4 INCONCLUSIVE.

## 6. Registered verdict
diff = TREATMENT resolved − CONTROL resolved on the 48 paired tasks.

| Condition | Verdict |
|---|---|
| diff ≤ −3 | **E4 LOSS** |
| \|diff\| ≤ 2 | **E4 TIE** |
| diff ≥ +3, cond2 and cond3 both hold | **E4 WIN** |
| diff ≥ +3, but another WIN condition fails | **E4 INCONCLUSIVE** |

- **cond2:** mutation failure rate(TREATMENT) ≤ 0.5 × mutation failure rate(CONTROL), each rate = failed mutation attempts ÷ all mutation attempts, pooled over the 48 tasks.
- **cond3:** no new major failure mode (the E3 rule): no category with CONTROL ≤ 2 affected tasks and TREATMENT ≥ CONTROL + 3.

## 7. Definitions
- **Mutation attempt:** a call intended to modify repository source, judged from the raw call: every edit-tool call (including missing-parameter rejections); a write to an existing tracked file or a new Python file under a package root; a template edit; a shell command that modifies source at the shell layer (in-place edits, redirection, working-tree git commands, patches, removing, moving, copying or touching a source path) or from Python; and any instrumented command after which source changed.
- **Failed attempt:** a tool, schema, shell or non-zero-exit error; a target mismatch; a malformed mutation; or a reported success whose expected change is absent.
- **Categories** (per-task presence feeds cond3): M_MALFORMED (missing parameter, corrupted keys or a syntax error in the edit); M_TARGET_MISMATCH (old text not found, or target missing); M_AMBIGUOUS (more than one match); M_EXEC_ERROR (any other failure); M_NO_EFFECT (reported success, expected change absent); M_IDENTICAL_RETRY (identical to the immediately preceding failed attempt); M_SILENT_CORRUPTION (reported success, but a sandbox path was written, other files changed or the new text is absent); M_SYNTAX_BROKEN (a changed Python file stops compiling). The E3 non-mutation categories also enter cond3: the time, call and turn caps; runaway calls (≥ 45 s); context-window-exceeded errors; task exceptions; empty final patches; and tool-error classes of other calls.
- **Descriptive only:** paired outcomes, E3-defined missing-match-string edits, malformed multi-line edits, retries, mutations by method, no-edit tasks, template adoption, caps, logging cost, E3 metrics. **Planned post-hoc:** re-verify intermediate source states of unresolved tasks to find working patches later damaged; write up every discordant task.

## 8. Amendment v2 (frozen before the 48-task run)
After v1 was frozen, a mechanical 4-task adoption pilot (TREATMENT only, public tasks outside the panel; its solve rate is not evidence and did not tune the prompt) exposed a classifier bug: v1 judged every Python heredoc that used the template's variable names by the template's rule, so a custom script that changed the target correctly was scored as a failed mutation. Such scripts are expected almost only in TREATMENT, so the bug biased cond2 against TREATMENT.

The amendment changes analysis code only. A template-named script counts as a template edit only if it performs the template's replacement; otherwise it is judged by effect: source changed → success; unchanged with exit 0 → failed, M_NO_EFFECT; unchanged with a non-zero exit → failed with the v1 category; no post-call state recorded → the exit status decides. Prompts, tasks, settings, orchestration, logging, V1–V7, the verdict rule and every threshold are unchanged; the amended code reproduces v1's results on E3 final-run data, and the pilot's label (ADOPTED WITH ISSUES) is unchanged.

## 9. Validation before the freeze
- **Parser replay:** 16/16 well-formed template calls byte-identical through the serving engine's own tool-call parser.
- **Sandbox battery, 9/9 gates PASS** (48 panel tasks plus 4 pilot tasks, real harness, real workspaces): 748/748 generated calls byte-identical after parsing; 676/676 positive edits byte-exact and touching only the target; 312/312 negative or corrupted shapes failed loudly with the file unchanged; 52/52 gold fixes reproduced through the tools and resolved end to end; logging read-only on 52/52; hook-on and hook-off reruns identical on 6 tasks; snapshot p95 25 ms.
- **Hazard probes:** an unquoted heredoc delimiter silently altered written text (3/3), and the harness silently rewrote a temporary-directory path in new text (3/3). A first battery version failed two gates only because of a bug in its own gold-patch parser, fixed without changing any prompt or experiment file.

## 10. Known risks (stated before the run)
- **Power:** identical configurations flipped 4–7 tasks between E3 runs; with about 7 discordant tasks and no real effect, ±3 occurs in roughly 15–20 % of runs in each direction. 15 control tasks never attempt an edit.
- **Strict matching:** the template lacks the edit tool's whitespace-tolerant and unescaping fallbacks.
- **Habit:** the model wrote all 230 E3 heredocs with an unquoted delimiter; if it drops the template's quotes, backticks, `$` and backslashes in new text are silently altered.
- **Path rewriting:** handled by the fallback rule, which fired on 1 of 171 gold hunks.
