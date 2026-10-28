# E6R preregistration (public summary): thinking-history mechanical pilot

**Small mechanical pilot (4 tasks per arm; measures model behaviour, not solve rate).**

> **Provenance.** Sanitized public summary written 2026-10-27, after the run. The frozen original is withheld because it
> contains restricted benchmark task identifiers and evaluation-platform details. SHA-256 of the original file and its UTC
> freeze time are listed so it can be verified if released.
>
> - Original file SHA-256: `cf128c6d36b0d902c0fb187fc352d4f493fed310df01132422d54931de8d465a`
> - Frozen: **2026-10-21T20:28:10Z** (UTC, from the original's freeze footer). Launched 2026-10-22T03:03:43Z.
> - The original's footer also lists SHA-256 values of the other frozen files (arm builder, run builder, report script,
>   request/response ledger, token-count step, both agent configurations, task list, static checks, request capture, report
>   tests). Those files are withheld.

## 1. Question (mechanics only)
Can bounded thinking run correctly and affordably in this harness with Gemma 4 31B, before any paired thinking experiment is
designed? Specifically: is reasoning actually produced; does vLLM 0.19.1 enforce the 512-token thinking budget; do tool calls
still parse; does the harness flow survive (no truncated turns, no context overflow); is earlier reasoning dropped or kept in
the history as configured; and what is the latency per call within the 3-minute budget.

**No performance verdict** is produced, and nothing is tuned from solves. The pilot is separate from E6A: E6A's rules,
configurations and analysis do not reference it.

## 2. Variants
| | THINK_DROP (runner arm CONTROL) | THINK_KEEP (runner arm TREATMENT) |
|---|---|---|
| prompts, tools, evaluation config | E3 treatment agent, byte-identical | same |
| temperature / top_p / top_k | 1.0 / 0.95 / 64 (server default, not sent) | same |
| thinking | on, 512-token thinking budget | same |
| earlier reasoning in history | **removed** before it enters the agent history | **kept**, attached to earlier assistant tool-call turns (as the model card recommends) |
| max output tokens | 8,192 | 8,192 |

The two variants differ only in whether earlier thoughts are kept.

## 3. Tasks and run shape
- **4 tasks**, public and gold-validated, **not** in the 48-task development panel; chosen earlier by a seeded rule before any
  model behaviour was seen.
- 8 jobs (4 tasks × 2 variants), variant order alternating per task, **one job at a time**.
- Budgets: 3 minutes, 50 tool calls, 150 turns, 90 s per command (same as the earlier thinking-off runs).
- Model `gemma-4-31b-it` (QAT W4A16), vLLM 0.19.1, TP 4, 4× NVIDIA L4.
- Added instrumentation: a read-only request/response ledger (sampling and thinking arguments, earlier turns carrying
  reasoning, finish reason, tool calls, reasoning text, token usage) and a post-run reasoning-token count with the served
  model's own tokenizer.

## 4. Validity (any failure → PILOT INVALID, no labels)
- PV1 run status VALID; PV2 host versions identical to the E4 run; PV3 8 result rows, each with ≥ 1 model call and a trace;
  PV4 trace / tool-log alignment.
- PV5 ledger coverage within [0.99, 1.01] × tool-bearing model calls per variant; ledger errors ≤ 1 %.
- PV6 the server's generation-config line appears exactly once in the server log.
- PV7 every tool-bearing request has temperature 1.0, top_p 0.95, 8,192 max completion tokens, thinking enabled with a
  512-token thinking budget, and no top_k, max_tokens, stop, penalties, seed or reasoning-effort field; both variants send the
  same key sets.

## 5. Mechanical checks (per variant, on completed tool-bearing calls)
| Check | Registered rule |
|---|---|
| K1 thinking active | ≥ 90 % of calls carry reasoning text |
| K2 budget enforced | max reasoning tokens ≤ 544 (512 + 32 for markers); tokenizer counts, else usage counts for ≥ 90 % of calls, else NOT EVALUABLE |
| K3 tool-call integrity | no-tool-call turns ≤ 5 %, and corrupted calls ≤ 15 % of traced calls |
| K4 harness flow | no call ends with finish reason `length`, and ≤ 4 context-window overflows |
| K5 history | THINK_DROP: no request carries earlier reasoning. THINK_KEEP: ≥ 90 % of requests with an earlier assistant turn carry reasoning on at least one of them |

A **corrupted call** (E3 definition) is a traced tool call with an argument name containing a quote, backslash, backtick or
special-token marker, or whose tool reply reports missing mandatory parameters.

**Labels:** K1 or K2 fails → **BROKEN**; K2 not evaluable → **NOT EVALUABLE**; K3–K5 all pass → **MECHANICALLY CLEAN**;
otherwise → **CLEAN WITH ISSUES** (listing failed checks).

**K6, descriptive only:** model-call latency (median, p90), calls per task, reasoning-token distribution and share of calls at
≥ 500 tokens, 3-minute caps, last-call prompt tokens, compactions, context overflows, solves.

## 6. Registered use of the result
- If THINK_KEEP is MECHANICALLY CLEAN, a later paired thinking experiment uses it; else, if THINK_DROP is clean, it uses
  THINK_DROP; else no paired thinking experiment until the cause is fixed.
- That experiment's per-task time budget may be set from K6 latency and calls per task only, never from solves.
- If K2 fails, thinking is not deployable as configured: report and stop.

## 7. Validation completed before the freeze (local, no GPU)
- Static checks: both configurations compile with the official harness; thinking on with budget 512 and temperature 1.0; the
  trees differ only in the history setting; prompts, evaluation config and tools equal the E3 treatment agent.
- Request capture against a recording stub: thinking fields present, no top_k, earlier reasoning present only under
  THINK_KEEP; the ledger leaves request bodies unchanged.
- 18 report unit tests plus an end-to-end smoke run on stand-in data.
- Not verifiable offline (and therefore measured by the pilot): server-side budget enforcement, how the chat template renders
  kept reasoning, and latency.

## 8. Known risks stated before the run
4 tasks is tiny and the labels are mechanical, not statistical; 3 minutes may be too short for thinking (a K6 finding, not a
failure); keeping thoughts grows the context faster (watched in K4 and K6).
