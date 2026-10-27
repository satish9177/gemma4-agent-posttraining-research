# E7 preregistration (public summary): strong inference-only baseline reproduction

> **Provenance.** Sanitized public summary written 2026-10-27, after the run. The frozen original is withheld because it contains restricted benchmark task identifiers and evaluation-platform details.
>
> - Original file SHA-256: `f79d7b678843fa4ada6125c11e5ca185a5cc2faad85df0f907b4e680c8e9c6e9` (also listed in the E8 freeze manifest, frozen 2026-10-24T18:08:41Z).
> - Frozen: **2026-10-24T10:03:06Z** (UTC); the original freeze manifest hashes 69 files.
>
> This summary restates the frozen design and adds no rules. Only the labelled note at the end was written after the run.

## 1. What E7 is, and what it is not

- **What it is:** a reference baseline: a publicly shared strong community configuration for Gemma 4 31B, run byte for byte as published on the fixed 48-task panel of E3–E6, to measure its solves, failure modes and projected 120-task runtime, and to decide by a pre-registered go/no-go rule whether it deserves an external evaluation run.
- **What it is not:** a causal experiment. Relative to the earlier thinking-off configuration (the E3 treatment) it changes eight things at once (thinking, thought history, time, call and turn budgets, command timeout, agent architecture, system prompt); no result may be attributed to any one of them. The three earlier valid thinking-off runs (15, 15, 13 of 48 solved) are a descriptive comparison only.

## 2. Configuration (reproduced unchanged)

| Setting | Earlier thinking-off configuration | E7 |
|---|---|---|
| Thinking | off | on, 4,096-token budget |
| Earlier thoughts kept in history | no | yes |
| Time / tool calls / turns per task | 3 min / 50 / 150 | 8 min / 28 / 80 |
| Command timeout | 90 s | 240 s |
| Agents | root agent + code-analyzer sub-agent | one agent, nine tools |
| System prompt | E3 prompt (4,645 characters) | its own prompt (6,323 characters), planned around 28 calls |
| Temperature / top_p / max output tokens | 0.2 / 0.95 / 8,192 | same |
| Model / adapters | Gemma 4 31B QAT W4A16 / none | same |

The four configuration files are pinned by per-file hashes; the run stops before any GPU work unless the files written to disk match exactly.

## 3. Pre-launch validation (local, no GPU; all passed)

Static checks S1–S6 (compiles as the harness loads it, with the settings above); request capture C1–C3 (every request to a local server stub carries the frozen sampling and thinking fields, no top_k and all earlier thoughts; logging hooks change nothing); run-script tests T1–T4 (a one-byte change or extra file stops the run); report unit tests 41/41 (17 vs 18 solves, each CF threshold, runtimes of 11.0 / 12.0 / 12.01 h, V1–V8 on synthetic runs); stand-in tests D1–D4 (earlier registered numbers reproduced).

## 4. Run design

- `gemma-4-31b-it` (QAT W4A16) on vLLM 0.19.1, tensor parallelism 4, 4× NVIDIA L4; a function-calling repository-agent harness built on Google's Agent Development Kit, each task sandboxed and graded by hidden tests.
- One arm, 48 tasks in frozen order, **one job at a time** (earlier runs used two concurrent jobs, so latency is not directly comparable).
- Runner reused from earlier valid runs, changed only to run one arm under a 480-minute task-loop deadline (reaching it means INVALID). Unchanged: health checks around every task, 15 s watchdog, abort as INVALID on any server failure or abnormal task end, compaction settings, harness verification.
- Read-only instrumentation; descriptive post-run patch apply / compile check and reasoning-token counts.

## 5. Validity (any failure: E7 INVALID, no decision)

| Check | Rule |
|---|---|
| V1 | Run status VALID: no abort, all 48 jobs executed, every task ended normally |
| V2 | 48 pre-task health checks ok; no abort or server-exit event |
| V3 | One result row per task: no exception, normal end, ≥ 1 model call, a trace |
| V4 | No model call failed with a model-server error |
| V5 | One job at a time, in the frozen order |
| V6 | Server log present; host package versions identical to the E4 run |
| V7 | In-run configuration check: exactly the pinned files, one arm, 48 tasks, one job at a time |
| V8 | Inference-config line logged once; every tool-bearing request has temperature 0.2, top_p 0.95, 8,192 tokens, thinking on with budget 4,096, no forbidden sampling keys; ledger coverage in [0.99, 1.01], errors ≤ 1 % |

Evaluability notes (never invalidate the run): X1 mutation log present, hook errors ≤ 1 %; X2 trace and tool logs align. If X2 fails, the repetition, near-repeat and first-edit readouts are NOT EVALUABLE.

## 6. Pre-registered go/no-go rule (not a causal WIN criterion)

**E7 PROMISING** iff all three hold: **≥ 18/48 solved**; **no catastrophic new failure mode**; **acceptable runtime feasibility**. Otherwise **E7 NOT PROMISING**, listing every failed condition. Either way: stop and report. PROMISING only justifies *asking* for approval of an external evaluation run.

**Catastrophic new failure mode** (any one):

| Flag | Definition | Earlier thinking-off runs |
|---|---|---|
| CF1 | Corrupted tool calls (E3 definition) > 15 % of traced tool calls | 6.4–10.2 % |
| CF2 | Turns without a tool call > 5 % of tool-bearing model calls without error | 0.27–0.57 % |
| CF3 | ≥ 5 of 48 tasks with a context overflow or a length-truncated tool-bearing response | 0–1 task |
| CF4 | New failure category: earlier runs' maximum ≤ 2 tasks and E7 ≥ 8 tasks | – |

CF4 uses the frozen per-task failure categories, computed identically for E7 and the three earlier runs (baseline = their maximum), with `CAP:*` budget-cap labels removed and a turn-budget end not counted as a task exception.

**Runtime feasibility:** P = 0.5 h + 120 × mean per-task wall time (sandbox setup, agent, verification) / 3600. P ≤ 11.0 h: **COMFORTABLE**; 11.0 < P ≤ 12.0 h: **TIGHT** (both acceptable); P > 12.0 h: **NOT ACCEPTABLE**. 12.0 h is the intended external evaluation's limit; its tasks come from other repositories, so this local projection can only flag a gross mismatch.

## 7. Descriptive readouts (registered; never in the decision)

Next to the three earlier runs: solves and overlap; no-edit tasks; final-patch classes; first-edit timing; no-progress, repeated and near-repeat calls; corrupted calls and missing-parameter rejections; turns without a tool call; latency and tokens; time, call and turn cap hits; compactions, overflows and truncations; short vs informative issue statements; patch apply / compile; runtime and projection; thinking mechanics; failure categories.

## 8. Interpretation rules stated before any data

- Identical earlier runs solved 15, 15 and 13 and differed pairwise on 2–7 tasks.
- 15 tasks have short issue statements and are almost never solved: the effective sample is about 33.
- One run is one draw: reaching 18 (≥ +3 over the best earlier run) would be neither a causal effect nor an estimate for other task sets, and local solve rates have been much higher than on held-out external tasks.
- Two panel tasks reference names only the reference patch introduces; all 48 reference patches resolve here, and the panel is kept unchanged.

## 9. Known risks named in advance

Runtime (section 6); edit-argument loss under thinking, reported by the community (CF1 and the corrupted-call readout); context growth from retained thoughts (CF3 and context readouts); generality, since the panel comes from three public Python repositories; unpinned client packages in the run image (request path checked on every request, V8).

---

**Note added in this public summary (post-hoc, not part of the frozen design).** After the run, two flaws were found while designing E8, and E8's preregistration documented them:
1. The CF4 exclusion removed `CAP:*` labels but not the harness's refusals of calls beyond the budget (`BudgetExceeded`), so a resource-budget outcome was counted as a semantic failure category.
2. The registered "call-cap hits" readout searched for error text that the harness never writes, so it reported 0 when the correct number was 20.

The registered E7 verdict, **E7 NOT PROMISING**, is unchanged. See [RESULTS.md](RESULTS.md).
