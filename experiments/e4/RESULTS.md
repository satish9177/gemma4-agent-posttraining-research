# E4 results: Tool-protocol reliability, edit protocol

**Status:** completed · run VALID · registered verdict **E4 TIE**. Frozen 2026-10-21T08:59:44Z (v1) and 2026-10-21T10:12:41Z (amendment v2); launched 10 s after the amendment freeze; completed 2026-10-21T12:42:42Z (2.5 h). Preregistration summary: [PREREGISTRATION.md](PREREGISTRATION.md).

## Research question
E3's prompt guidance fixed read corruption but not edit corruption. Does moving source edits from the structured edit tool to one shell-command string (a fixed Python-heredoc template that asserts a unique match and prints the diff) reduce failed edits and increase tasks resolved?

## Frozen configuration
Identical to the E3 final run: `gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4. Temperature 0.2, top_p 0.95, at most 8,192 output tokens, **thinking off** (thinking budget 0). Per task: 3 minutes, 50 tool calls, 150 turns, 90 s per command. The fixed 48-task development panel in the frozen order; one inference server, arm order alternating by task, 2 jobs at a time, health checks and abort-on-failure. A read-only mutation log was added identically in both arms.

## Manipulation
- **CONTROL:** the E3 final run's TREATMENT configuration, byte-identical.
- **TREATMENT:** CONTROL plus a "Safe Editing" section appended to the system prompt (paraphrased in the preregistration). Nothing else changed.

## Validity gates
| Gate | Outcome |
|---|---|
| V1 run status VALID | PASS |
| V2 health log complete, no abort or server exit | PASS (691 checks, 0 failed attempts) |
| V3 every task executed normally in both arms | PASS (96/96 jobs) |
| V4 no model-server failure | PASS (0 failed calls; server log: 3,289 chat requests answered 200, 0 answered 5xx, 2 answered 400 as context-length rejections, one per arm) |
| V5 arm-order rule | PASS |
| V6 server log persisted; host versions identical to the E3 final run | PASS |
| V7 mutation log in both arms, hook errors ≤ 1 % | PASS (843 CONTROL and 670 TREATMENT records, 0 hook errors; mean 7.5 ms per instrumented call) |

## Result

| | CONTROL | TREATMENT |
|---|---|---|
| solved | 13/48 | 14/48 |
| diff (T − C) | | +1 |
| mutation attempts / failed / successful | 154 / 85 / 69 | 78 / 24 / 54 |
| mutation failure rate (cond2) | 85/154 = 55.2 % | 24/78 = 30.8 % (ratio 0.56; threshold ≤ 0.5) |
| tasks with M_NO_EFFECT (cond3) | 0 | 3 (meets the new-major-failure-mode rule) |

**Paired outcomes:** both 10 / control-only 3 / treatment-only 4 / neither 31.

**Exact McNemar p, two-sided = 1.0 (descriptive only;** not the registered decision rule). It is the exact binomial test on 3 vs 4 discordant pairs.

## Registered verdict
> E4 VERDICT (pre-registered): E4 TIE

diff +1 lies inside ±2, so the verdict is TIE whatever cond2 and cond3 show. For the record, both would also have failed: the failure-rate ratio was 0.56, not ≤ 0.5, and M_NO_EFFECT went from 0 to 3 tasks.

## Post-hoc (not registered)
- **The mechanism worked.** TREATMENT used the template for all 69 template edits and never called the edit tool, not even as the fallback. Edits missing the match string (E3 definition) fell from **83 calls in 7 tasks to 0**. Every template command was well-formed, with no fallback-rule violations. Identical retries after a failed edit fell from 63 calls in 6 tasks to 17 in 1. E3-defined corrupted calls: 168/1,650 (10.2 %) vs 66/1,499 (4.4 %).
- **It did not move resolution.** All 7 CONTROL tasks with missing-match-string corruption also failed in TREATMENT: 2 never reached an edit before the cap, 4 made clean edits that did not fix the issue, and 1 looped. The corruption sat in tasks that were failing for other reasons: localization and fix quality.
- **New failure mode: silent no-op edits** (M_NO_EFFECT, 20 calls in 3 tasks). The template accepts identical old and new text, exits successfully and prints the cumulative diff, which can show earlier changes. In one task the model re-sent the same no-op edit 18 times until the cap; the edit tool would have refused it. The other 2 such calls were heredoc scripts that wrote nothing.
- **Cost.** The template was about 37 % longer per edit (mean 1,140 vs 833 characters) and TREATMENT produced about 12 % more output per task. 3-minute caps rose from 12 to 20, no-edit tasks from 16 to 23, empty final patches from 13 to 17. Part of this came from loops in 3 treatment tasks: a no-op edit ×18, a reproduction probe ×37, whole-file re-reads ×25.
- **Discordant tasks.** In all 3 control-only tasks TREATMENT never edited: a corrupted ranged read repeated 32 times; a reproduction probe repeated 37 times (written in the template's heredoc form); a whole-file read loop. In all 4 treatment-only tasks both arms edited and TREATMENT's fix was right: CONTROL submitted a wrong change after 27 s where TREATMENT re-read first; TREATMENT's first template edit failed loudly as ambiguous, it rebuilt the old text with more context and resolved; one task had flipped the other way in the E3 final run (likely noise); and in one, CONTROL damaged a working patch (next item).
- **Working patches later damaged.** A separate check re-verified 86 patches (every distinct intermediate source state of each unresolved task, 19 CONTROL and 11 TREATMENT, plus their final patches) with the harness's own verifier: 0 errors, and all 30 re-verified final patches agreed with the run. Exactly 1 task was damaged, in CONTROL: its state after the 3rd edit resolved the task, and the 4th edit broke it. No unresolved TREATMENT task ever held a working state.
- **Noise and order.** The same configuration (E4 CONTROL = E3 TREATMENT) solved 15, 15 and 13 in E3 run 1, the E3 final run and E4; 4 tasks flipped between the E3 final run and E4. Solved when run first / second: CONTROL 6/24 and 7/24; TREATMENT 9/24 and 5/24.

## Limitations
- The +1 difference is well inside run-to-run noise. The preregistration estimated that, with about 7 discordant tasks and no real effect, ±3 occurs in roughly 15–20 % of runs in each direction.
- Mutation attempts and their failures are classified by custom analysis code, not by a harness signal. Amendment v2 changed that classification after the adoption pilot (analysis code only, before the 48-task run).
- The arms used different editing methods, so their mutation attempts (154 vs 78) differ in kind as well as number.
- Tested only as prompt text, with one model, thinking off, temperature 0.2 and a 3-minute budget; the 48 tasks come almost entirely from two repositories.

## What changed because of this result
- The edit template was not carried forward: the E4 CONTROL (the E3 treatment configuration) stayed the frozen control for E5.
- Edit corruption sat in tasks failing for other reasons, and the discordant tasks traced to exploration loops and fix quality. Work moved from tool-call protocol to loops: the next experiment (E5) tested progress rules against no-progress loops.
