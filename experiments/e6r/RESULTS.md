# E6R results: thinking-history retention pilot

> **Small mechanical pilot (4 tasks per arm; measures model behaviour, not solve rate).**

**Status:** VALID · THINK_DROP **BROKEN** · THINK_KEEP **MECHANICALLY CLEAN**.
Frozen 2026-10-21T20:28:10Z; launched 2026-10-22T03:03:43Z; completed about 03:39Z (0.57 h). Preregistration summary:
[PREREGISTRATION.md](PREREGISTRATION.md).

## Research question
With thinking on, does the agent keep thinking, stay within budget and keep valid tool calls when earlier thoughts are
**dropped** from the conversation history versus **kept**?

## Frozen configuration
`gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, TP 4, 4× NVIDIA L4. Temperature 1.0, top_p 0.95, top_k 64 (server default),
thinking on with a 512-token thinking budget, 8,192 output tokens. 3 minutes, 50 tool calls, 150 turns, 90 s per command.
4 gold-validated public tasks outside the 48-task panel; 8 jobs, one at a time, alternating order.

## Manipulation
Only the history setting differs: THINK_DROP removes earlier reasoning before it enters the history; THINK_KEEP keeps it on
earlier assistant tool-call turns.

## Validity gates
| Gate | Outcome |
|---|---|
| PV1 run status VALID | PASS (8/8 jobs normal; 110 health checks, 0 failed) |
| PV2 host versions identical to E4 | PASS |
| PV3 8 result rows with model calls and traces | PASS |
| PV4 trace / tool-log alignment | PASS |
| PV5 ledger coverage and errors | PASS (104/104 and 80/80 calls; 0 errors) |
| PV6 generation-config line once | PASS |
| PV7 thinking manipulation verified | PASS (0 non-conforming requests; key sets equal) |

## Result
| Check (registered rule) | THINK_DROP (earlier thoughts dropped) | THINK_KEEP (earlier thoughts kept) |
|---|---|---|
| K1 thinking active (≥ 90 % of calls) | **fail: 48 / 103 = 47 %** | pass: 77 / 77 = 100 % |
| K2 budget enforced (max ≤ 544 tokens) | pass: max 518 | pass: max 516 |
| K3 no-tool-call turns (≤ 5 %) | 5 / 103 | 2 / 77 |
| K3 malformed (corrupted) tool calls (≤ 15 %) | 6 / 99 | 0 / 75 |
| K4 length finishes / context overflows | 0 / 0 | 0 / 0 |
| K5 history as configured | pass | pass |

K6 (descriptive): calls per task 25.8 vs 19.2; median model call 2.8 s vs 3.9 s (p90 16.2 s vs 15.7 s); median reasoning
tokens 0 vs 70; calls at ≥ 500 reasoning tokens 14.6 % vs 13 %; 3-minute caps 1 vs 3 of 4 tasks; median last-call prompt
10,821 vs 14,638 tokens; compactions 2 vs 4.

**Solves: 2 / 4 vs 1 / 4. Descriptive only; with 4 tasks this says nothing about performance.**

## Registered labels
```
PILOT STATUS: VALID
CONTROL = THINK_DROP:    BROKEN
TREATMENT = THINK_KEEP:  MECHANICALLY CLEAN
```
Registered consequence: THINK_KEEP is MECHANICALLY CLEAN, so any later paired thinking experiment uses it; its time budget
may be set only from the latency figures (about 19 calls in 3 minutes, 3 of 4 tasks at the cap), never from solves.

## Post-hoc (not registered)
- **Dropping thoughts makes thinking fade.** Under THINK_DROP the model reasoned on the first call of every conversation
  (5 / 5) but on only 43 of 98 later calls, typically for several turns and then mostly not at all. Under THINK_KEEP every
  call contained reasoning. This fits in-context imitation: once the history shows assistant turns without thoughts, the
  model stops producing them.
- **The thinking budget binds on a minority of calls:** 15 of 103 (DROP) and 10 of 77 (KEEP) reached ≥ 500 reasoning
  tokens; none exceeded 518.
- For comparison, the thinking-off configuration had 6–10 % corrupted calls in earlier runs; THINK_KEEP had none here.

## Limitations
- 4 tasks, one run per variant; mechanical labels only, no statistical claim.
- One thinking budget (512 tokens) and a 3-minute budget that capped 3 of 4 THINK_KEEP tasks.
- Client library versions in the run environment differed from the local validation; the run itself confirmed that the
  thinking fields reached the server.

## What changed because of this result
- Retaining earlier thoughts became a requirement for every later thinking-on configuration; the later thinking-on runs
  (E7, E8) keep reasoning in the history.
- No full paired thinking run was started under E6R.
- Because E5 and E5G ran with thinking **off**, their broad conclusion that the loop behaviour was intrinsic to the policy
  was later superseded by the thinking-on runs (E7, E8), which showed far fewer no-progress calls. Those runs also changed
  budgets and prompts, so the drop cannot be credited to thinking alone.

## Related: E6A (held, not run)
E6A was a paired 48-task experiment on the development panel: the frozen thinking-off agent at temperature 0.2 versus the
identical agent at temperature 1.0 (with top_p 0.95 and top_k 64, the model card's standard sampling). It asked whether the
repetition behaviour is a product of near-greedy decoding, and registered a solve-count verdict (E6A LOSS / TIE / WIN /
INCONCLUSIVE at ±3 tasks, with no-new-failure-mode and tool-call-integrity conditions: corrupted-call rate ≤ control
+ 5 points, no-tool-call turn rate ≤ control + 1.5 points) and a mechanism verdict on r = NNI rate ratio (NO EVIDENCE if
r > 0.8; TRANSFORMED if r ≤ 0.8 with a near-repeat substitution flag; TEMPERATURE DRIVES REPETITION if r ≤ 0.5; PARTIAL
EFFECT if 0.5 < r ≤ 0.8).

- Preregistration frozen 2026-10-21T20:18:43Z (SHA-256 `b94f9a3345f622664a833a8615dc0f6f98a688f47e2019005d32041b084b9ee2`);
  verdict-structure amendment v2 frozen 2026-10-21T20:54:34Z (SHA-256
  `b3cc490549438d701e421552b948c033fabc8dc435479fbd13876986b3d58cdc`). Both originals are withheld for the same reasons.
- **Status: held, never launched. No E6A data exist and no E6A conclusion is drawn.**
