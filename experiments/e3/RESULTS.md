# E3 results: Tool-protocol reliability, read serialization

**Status:** completed. One design, three runs: **run 1** VALID; **confirmation run** INVALID (archived here, excluded from every conclusion); **final run** VALID. Rules and thresholds: [PREREGISTRATION.md](PREREGISTRATION.md).

## Research question
With thinking off, Gemma 4 31B often emitted malformed tool calls, most often ranged file reads with corrupted argument keys that never returned the requested lines. Does short tool-protocol guidance, chiefly reading line ranges through a shell command, reduce malformed calls and increase tasks resolved?

## Frozen configuration
- `gemma-4-31b-it` QAT W4A16 checkpoint; vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4, 32,768-token context.
- Temperature 0.2, top_p 0.95, at most 8,192 output tokens, thinking budget 0 (thinking off).
- Per task: 3 minutes, 50 tool calls, 150 turns, 90 s per shell command.
- A function-calling repository agent built on Google's Agent Development Kit (nine tools, a code-analysis sub-agent), sandboxed and graded by hidden tests; pinned versions identical across runs.
- The fixed 48-task development panel (three public Python repositories: FastAPI 24, Rich 23, Requests 1), same order in every run, 2 tasks in parallel.
- Run 1 and the confirmation run ran the arms one after the other with a fresh server per arm; the final run used one server and alternated arm order by task.

## Manipulation
**CONTROL:** the frozen baseline agent configuration. **TREATMENT:** the same plus a short system-prompt section asking the agent to read line ranges with a shell command instead of the read tool's range arguments, to keep the edit tool's match string to a few exact lines copied from the file, and not to resend a call unchanged after an argument, schema or tool error. Nothing else differed.

## Validity gates
| Run | Outcome |
|---|---|
| Run 1 | No gates registered. All 48 tasks ran in both arms; a later check found 0 inference-server errors in 3,440 model calls. |
| Confirmation | The registered checks passed (48 paired tasks, 48 traces per arm, identical host versions), but they did not cover server health. About 2,623 s into the TREATMENT arm the inference server stopped accepting connections and never recovered. The last 12 TREATMENT tasks failed with connection errors, 11 of them without a single successful model call. Server output was not captured, so the cause is unknown. **INVALID / COMPROMISED.** |
| Final | All six checks V1–V6 **PASS**: 96/96 jobs ended normally; the order rule held; 670 health checks, 0 failed attempts; the server answered 3,449 chat requests with 200, 0 with 5xx, and 4 with 400 (context-length rejections, the normal context-window-exceeded case). |

## Result

| | Run 1 | Confirmation (INVALID) | Final |
|---|---|---|---|
| CONTROL solved | 9/48 | 11/48 | 12/48 |
| TREATMENT solved | 15/48 | 9/48 | 15/48 |
| diff (T − C) | +6 | −2 | +3 |
| corrupted-call rate, CONTROL | 385/1,653 (23.3 %) | 332/1,651 (20.1 %) | 350/1,789 (19.6 %) |
| corrupted-call rate, TREATMENT | 111/1,576 (7.0 %) | 114/1,215 (9.4 %)ᵃ | 95/1,491 (6.4 %) |
| `old_string_not_found` tasks, C → T | 0 → 3 | 0 → 0 | 3 → 4 |
| paired: both / control-only / treatment-only / neither | 9 / 0 / 6 / 33 | 7 / 4 / 2 / 35 | 11 / 1 / 4 / 32 |
| exact McNemar p, two-sided (**descriptive only**) | 0.03125 | not reported | 0.375 |

ᵃ Includes the 12 outage tasks.

The p-values are descriptive, not the registered decision rule: exact binomial tests on the discordant pairs (0 vs 6, and 1 vs 4).

**Descriptive aggregate of the two valid runs** (registered as secondary; cannot change a verdict; each task appears twice, so no test is computed):

| | CONTROL | TREATMENT |
|---|---|---|
| solved | 21/96 | 30/96 |
| corrupted-call rate | 735/3,442 (21.4 %) | 206/3,067 (6.7 %) |
| discordant pairs won by this arm (run 1 + final) | 0 + 1 = 1 | 6 + 4 = 10 |
| tasks whose outcome flipped between the two valid runs | 7 | 4 |

## Registered verdicts
- **Run 1: "INCONCLUSIVE (not a win)".** diff +6 and the corruption rate was more than halved, but `old_string_not_found` went from 0 to 3 tasks, exactly meeting the new-major-failure-mode rule.
- **Confirmation run: no verdict (run INVALID).** Its frozen analysis printed "E3 NOT CONFIRMED" (diff −2), but the run was ruled "INVALID / COMPROMISED" and that label is void. All 4 of its control-only tasks were among the 12 TREATMENT tasks lost to the outage.
- **Final run: "E3 CONFIRMED".** diff +3 (condition 1); corruption 6.4 % vs 19.6 % (condition 2); `old_string_not_found` 3 → 4 tasks, which does not trigger condition 3. The procedure also re-runs the unchanged run-1 analysis as an intermediate step, which prints "E3 WIN" for these numbers; the rule registered for this run is the confirmation rule.

## Post-hoc observations (not registered)
- **Reads improved; edits did not.** Broken range-key reads fell from 326 to 71 calls (run 1) and from 301 to 54 (final); shell line-range reads rose from 7 to 74 and from 11 to 98. Edit calls missing the match string did not improve: 59 calls in 5 tasks → 40 in 8 (run 1); 49 in 4 → 41 in 5 (final).
- **The no-identical-retry guidance failed.** Immediate identical retries after a tool error rose from 70 calls in 5 tasks to 156 in 11 (run 1) and from 85 in 5 to 126 in 10 (final), mostly repeated failing shell commands.
- **Run 1, treatment-only tasks.** In three, CONTROL issued 21, 38 and 41 malformed range reads and never reached the target region, while TREATMENT read it and edited (in one, only after 18 identical edit calls missing the match string). In the other three, CONTROL explored without editing or looped (one failing command about 22 times; one identical probe about 32 times); two of these had been solved by the same baseline configuration in an earlier run.
- **Run 1, `old_string_not_found`.** All 3 tasks were unresolved in both arms. Causes: a placeholder comment inside the match string, and multi-line blocks flattened into one line with literal backslash-n escapes (repeated 8 times in one task).
- **Noise.** CONTROL solved 9 in run 1 and 10 in an earlier baseline run of the identical configuration, with 7 tasks flipping. One task was treatment-only in both valid runs.
- **Order (final run).** Solved when run first / second: CONTROL 4/24 and 8/24; TREATMENT 9/24 and 6/24. This tracks task parity, not arm order: on odd tasks CONTROL 4 vs TREATMENT 6; on even tasks 8 vs 9.

## Limitations
- The confirming difference, +3, sits exactly on the threshold, and byte-identical configurations flipped 4–7 tasks between runs.
- The verdict is a composite screen, not a significance test.
- One model size, thinking off, short budgets; the 48 tasks come almost entirely from two repositories.
- Run 1 had no registered validity gates.
- The final run changed orchestration relative to run 1, so the two valid runs are not identical procedures.

## What changed because of this result
- The TREATMENT configuration became the control for E4 and later experiments.
- Edit corruption was not reduced, so E4 targeted the edit protocol directly.
- The final run's validity regime (health checks, abort on failure, persisted server log, alternating arm order, validity checks before any verdict) became the standard orchestration for later paired runs.
