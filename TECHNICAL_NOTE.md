# What preregistered experiments taught me about Gemma 4 as a coding agent

*Satish Kommanaboina · independent researcher · technical note, 27 October 2026*

**Claim labels:**
- **[FACT]**: stated in a cited public source.
- **[LOCAL]**: measured in the preregistered experiments of this repository.
- **[INFERENCE]**: my reasoning from those.
- **[HYPOTHESIS]**: to be tested.

## Abstract

Between 17 and 27 October 2026 I ran a series of preregistered, hash-frozen experiments on Gemma 4 31B as a repository-level coding agent. The setup was a function-calling harness on a fixed 48-task panel of Python issues, with serving on 4× NVIDIA L4.

Five lessons stand out:
1. **Gemma 4's thinking depends on its history.** Dropping earlier thoughts from the context made thinking fade to 47% of calls, against 100% when they were kept. This comes from a small mechanical pilot.
2. **Tool-protocol reliability had to come first, but it was not enough.** Changes that removed most corrupted tool calls moved solves by +3 and +1 of 48.
3. **A reproduced thinking-on configuration is a strong inference-only baseline:** 19–21 of 48.
4. **Extra tool calls produced real late fixes,** but a small, non-significant gain overall: 21 → 24 of 48, exact McNemar p ≈ 0.25. The registered mechanism was not confirmed.
5. **Identical configurations flip 2–4 tasks between runs,** so effects of about 3 tasks on 48 cannot be distinguished from noise.

The remaining failures are wrong localization and wrong fixes, so the next lever is weight-level post-training. The public record warns that agent SFT on Gemma 4 often fails for reasons that are not capacity. I therefore propose a seeded study of when it starts to help, with three variables: data scale, reasoning retention, and whether the data come from the same scaffold. It runs after an audit confirming that the served adapter is the trained adapter.

## 1. Motivation

- **[FACT] Gemma 4 31B is a strong open base for coding agents.** Third-party runs report SWE-bench Verified around 66.6% for 31B with thinking. The harnesses differ, so only the size ordering is safe to use.
- **[FACT] Public SFT attempts mostly failed, mostly for reasons other than capacity.** Attempts to improve Gemma 4 repository agents with SFT tied or lost against untrained or prompt-only baselines. Examples include several hundred own-agent trajectories on 31B, 300–2,300 trajectories converted from other agent scaffolds on 31B, and 170 teacher trajectories on E4B. The authors attribute the failures to too little data, scaffold or format mismatch, a training/serving thinking mismatch, and small evaluations.
- **[FACT] CyberForge is the main controlled positive result.** It trained Gemma 4 on several hundred to about 1,000 oracle-verified trajectories collected in the same scaffold used at test time. For 12B: 8.7% untrained, **3.6% at 220 trajectories**, 12.1% at 440 and 16.0% at 880. The domain is C/C++ vulnerability repair, there was one training seed, and reasoning handling was held fixed.
- **[FACT] Serving can silently break adapters.** Gemma 4 adapters have been reported to load in vLLM with no effect, or with only 75–80% of their effect. A `v_proj` LoRA target skips the global attention layers of 12B, 26B and 31B.

Sources are in [docs/evidence-map.md](docs/evidence-map.md).

Before spending compute on training, I wanted to know how strong a carefully run inference-only agent is, and which of its failures training would need to fix.

## 2. Experimental setup

- **Model.** `gemma-4-31b-it`, QAT W4A16 checkpoint, served by vLLM 0.19.1 with tensor parallelism 4 on 4× NVIDIA L4. One inference server per run; one agent job at a time.
- **Agent harness.** A function-calling repository agent built on Google's Agent Development Kit, with nine tools: shell command, file read, edit and write, status, patch submission, and three code-search tools.
  - Each task runs in its own sandbox.
  - Success means the hidden tests pass on the submitted patch.
  - Budgets: tool calls, wall-clock minutes and turns.
- **Panel.** 48 tasks, sampled with a fixed seed from 101 gold-validated tasks drawn from 115 candidates. The gold patch must pass. The tasks come from three public Python repositories: FastAPI 24, Rich 23, Requests 1.
  - The same 48 tasks, in the same order, were used from E3 to E8.
  - By E8 the panel was heavily inspected, so it is now a development panel, not a held-out test.
- **Protocol** ([docs/methodology.md](docs/methodology.md)). Every experiment had:
  - a preregistration and a SHA-256 manifest of every input, frozen before launch;
  - paired arms on the same tasks, alternating arm order per task;
  - validity gates checked from the run's own logs, including a check that the manipulation took effect;
  - registered verdict rules applied by an analysis script frozen before the run.

  Invalid runs produce no verdict and are archived.

## 3. Why harness reliability came first (E3, E4)

**[LOCAL]** Early runs had thinking off. A large share of tool calls were malformed: argument keys corrupted, and range arguments silently ignored so that every read returned the top of the file. Such failures look like model incompetence but are protocol failures.

**E3: read serialization.** Prompt guidance told the model to read line ranges with a shell command instead of the read tool's range arguments. Three runs:

| Run | Corrupted calls | Solves (C → T) | Registered verdict |
|---|---|---|---|
| Run 1 | 23.3% → 7.0% | 9 → 15 (+6) | **INCONCLUSIVE**: a new failure category (edit "old string not found") appeared in exactly the number of tasks the rule flags |
| Confirmation | — | — | **INVALID**: the inference server stopped accepting connections partway through the treatment arm; excluded, archived |
| Final | 19.6% → 6.4% | 12 → 15 (+3) | **CONFIRMED** at exactly the +3 threshold. Paired 11 / 1 / 4 / 32; exact McNemar p = 0.375, descriptive |

**E4: edit protocol.** A different editing method removed the dominant edit failure. Missing-argument edits fell from 83 calls in 7 tasks to **0**. Solves were 13 vs 14, registered **TIE**. A new failure mode appeared: silent no-op edits, in 3 tasks.

The finding that matters:
- **[LOCAL]** All 7 tasks that suffered edit corruption in the control arm still failed in the treatment arm. Two never reached an edit; four made clean edits that did not fix the issue; one looped.
- **[INFERENCE]** Once protocol errors are removed, what is left is *competence*: finding the right place and writing the right fix. Prompt changes did not move that.

**Loop control (E5, E5G; thinking off).**
- **[LOCAL]** Prompt rules against repeated no-progress actions reduced no-progress calls to 0.73× of baseline (42.9% vs 59.1% of calls on 10 always-looping tasks). The preregistered bar was ≤ 29.5%: **NO-GO**.
- **[LOCAL]** A host-side guard that blocked exact repeats did not change the model's next action. In 9 of 10 blocked chains the model re-sent the identical call (median 9 more attempts), and the attempted-repeat rate moved only from 43.1% to 40.6%. Registered: **LOOPS REMOVED: NO**.
- **[INFERENCE]** With thinking off, in-context control signals did not steer the repetition. These runs are now superseded by the thinking-on results below, which had far fewer no-progress calls. That comparison is across different configurations and task sets, so it is not a controlled test.

## 4. The thinking-history experiment (E6R)

Gemma 4 emits reasoning in a separate thought channel. **[FACT]** Google's formatting guidance says thoughts must be kept in the history between function calls within a turn. Some serving and client stacks drop them.

**[LOCAL]** E6R was a *mechanical* pilot: 4 tasks per arm, thinking budget 512 tokens, temperature 1.0. The arms differed only in whether earlier assistant thoughts were kept in the request history.

| | Thoughts dropped | Thoughts kept |
|---|---|---|
| Calls with thinking active | **48/103 (47%)** | **77/77 (100%)** |
| Registered label (≥ 90% required) | **BROKEN** | **MECHANICALLY CLEAN** |
| Corrupted tool calls | 6/99 | 0/75 |
| Thinking on the first turn of a task | 5/5 | — |
| Thinking on later turns | 43/98 | 77/77 |

With thoughts dropped, the model thought for a few turns and then mostly stopped. **[INFERENCE]** This fits in-context imitation: a history full of thought-free assistant turns teaches the model to stop thinking.

That leads to an untested training question:
- **[HYPOTHESIS]** If trajectories with the thoughts stripped are used as SFT targets, thinking may fade *in the weights* even when inference enables thinking. Thought retention would then matter for training data, not just for serving.

The pilot says nothing about solve rate. Solves were 2/4 vs 1/4, descriptive only.

## 5. A strong inference-only baseline (E7)

**[LOCAL]** E7 reproduced a publicly shared thinking-on configuration for Gemma 4 31B:
- thinking budget 4,096 tokens, thoughts kept in history;
- temperature 0.2, top-p 0.95;
- 28 tool calls, 8 minutes and 80 turns per task.

It solved **19/48**, against 9–15/48 in the earlier thinking-off configurations. That comparison is confounded by prompt and budget differences, so it is not a controlled thinking ablation.

E7's registered verdict was **NOT PROMISING**, because a catastrophic-failure check fired. While preparing E8, I found that this check counted call-budget refusals as a *semantic* failure category. A related readout reported 0 tasks hitting the call cap; the correct number was 20.

The registered verdict is kept unchanged. The corrected measurement was used only from E8 on, under a new preregistration.

## 6. The tool-budget experiment (E8)

**[LOCAL]**
- **Motivation.** In E7, 20 of 48 tasks used all 28 calls. Nine kept requesting calls after the limit, and 7 were still editing at calls 25–28. Time was not binding for most of them: the median capped task had 256 s left.
- **Design.** A paired test of 28 vs 36 tool calls. The only change was the budget value in the configuration. Validity check V9 confirmed in the run that each arm enforced and announced its own budget. A preregistered limitation: the system prompt still said "28 calls" in both arms.

| | 28 calls | 36 calls |
|---|---|---|
| Solved / 48 | 21 | **24** |
| Paired: both / 28-only / 36-only / neither | 21 / 0 / 3 / 24 | |
| Exact McNemar p (descriptive) | **≈ 0.25** | |
| Corrupted tool calls | 2.2% | 1.6% |
| Projected runtime, 120-task evaluation (planning metric) | 10.84 h | 10.82 h |

**Registered verdicts.**
- Competitive: **WIN**. Δ ≥ +3, no catastrophic failure, runtime within budget.
- Mechanism: **BUDGET BOTTLENECK NOT CONFIRMED**. The useful-late-work criterion held: 7 tasks changed their final patch after call 28, and 3 solves came from decisive edits after call 28. The criterion requiring at least a 6-task drop in call-limit endings failed: the drop was 16 → 11, i.e. 5.

**[INFERENCE]**
- Extra calls produced real late fixes, but the overall effect is small and not significant on 48 tasks.
- The two verdicts were registered to be independent, and they are reported that way.
- I do not claim that more calls help in general.

## 7. A runtime lesson

**[LOCAL]** An external evaluation of the 36-call configuration, on a larger and different task set, exceeded its aggregate runtime budget twice. The two runs were byte-identical and on different days. The local projection had been 10.8 h against a 12 h budget.

Per a pre-specified rule there was no third attempt, and the configuration was classified operationally unsafe. No performance conclusion is drawn from those runs.

**[INFERENCE]** Local runtime projections did not include the tail behaviour of a different task distribution. A margin of about 10% was not enough.

**[LOCAL] E9** tested runtime directly: a paired 8- vs 7-minute cap at 32 calls on an 8-task stress panel chosen by a deterministic rule from E8 traces. The run was VALID and the registered decision is **MIXED**.
- Every condition for preferring 7 minutes passed except "no new failure mode": the 7-minute arm ended with an empty final patch on 4 tasks, the 8-minute arm on none. None of those 4 tasks was solved by the 8-minute arm either.
- No solve and no useful action needed minute 8. Where the late-call region (calls 28–32) was reached, it was reached before minute 6, so it depended on the call budget, not the clock.
- Most of the 10.5% panel time saving was run-to-run variation; the cap itself removes at most about 60 s from a long job. A post-hoc what-if on E8's wall times puts a 7-minute cap at about 10.3 h for 120 tasks, still above the 9.5–10.0 h target set after the overruns.

**[INFERENCE]** In this pilot, the late work that mattered tracked the call budget rather than the clock. That is consistent with the planned study's choice of call and token budgets with no wall-clock cap, but an 8-task pilot cannot establish it on its own.

## 8. Negative and null results, in one place

| Experiment | Registered outcome |
|---|---|
| E3 run 1 | INCONCLUSIVE (new-failure-mode flag) |
| E3 confirmation | INVALID (server outage), excluded |
| E4 edit protocol | TIE (13 vs 14) |
| E5 progress-rules prompt | NO-GO |
| E5G progress guard | LOOPS REMOVED: NO; BEHAVIORAL PROGRESS CREATED: NO |
| E6R thoughts-dropped arm | BROKEN |
| E7 | NOT PROMISING (registered; criterion later found flawed) |
| E8 | Mechanism NOT CONFIRMED |
| E8 external follow-up | Runtime budget exceeded twice; classified unsafe |
| E9 runtime pilot | MIXED: no configuration preferred (new empty-patch failure mode in the 7-minute arm) |

These are kept because they constrain the next step as much as the positive results do.

## 9. What remains unanswered

- **[INFERENCE]** The inference-time levers I could test reached roughly half the panel, with small and noisy increments. The residual errors are localization and fix quality: weight-level problems.
- **[FACT]** The public record shows that agent SFT on Gemma 4 can easily make things worse. Its documented failure modes are too few trajectories, scaffold mismatch, thinking mismatch and broken serving.

Nobody has published:
1. a seeded SFT data-scaling curve for any Gemma 4 size on Python repository tasks;
2. a test of whether a thinking-on Gemma agent must be trained on its own reasoning channel;
3. a same-task comparison of self-generated, same-scaffold data against freely available converted trajectories.

## 10. Proposed post-training study

Full design: [RESEARCH_PLAN.md](RESEARCH_PLAN.md).

- **Phase 0 (gate).** Verify that vLLM runtime LoRA reproduces the merged adapter for Gemma 4, and assert target-module counts.
- **Evaluation, in two separately reported tiers.**
  - **Tier A (primary):** Python tasks created on or after Gemma 4's release, from repositories absent from training, with gold patches validated twice. Only 62 such tasks are published ([inventory](analysis/post_release_task_inventory.md)). They are kept by removing their 14 shared repositories from training, and topped up by mining pull requests created after 12 May 2026. The target is at least 200 gold-valid tasks. The realized size is frozen before training, power is recomputed from it, and the post-release date is not relaxed ([mining plan](analysis/post_release_mining_plan.md)).
  - **Tier B (secondary):** tasks created after the January 2025 pretraining cutoff but before release; never called post-release (806 published candidates).
  - **Feasibility (27 Oct 2026, counts only):** 12,913 candidate pull requests pass the filters in repositories with a known working environment. Whether at least 200 become gold-valid tasks depends on a conversion rate that only building and validating them can measure. It needs about 1.3% with no per-repository cap and about 5.6% with a cap of 10; in the published window, a curated public task set included 1.8% of comparable candidates. A CPU-only pilot measures the rate before anything is frozen.
- **RQ1.** 12B LoRA SFT on 200 / 400 / 800 / 1,600 verified Gemma 4 31B trajectories from the same scaffold, 3 seeds each.
  - **[HYPOTHESIS]** No gain at 200; a Holm-significant gain at some size ≤ 1,600.
- **RQ2.** Thoughts kept vs stripped in the training targets, at 800.
- **RQ3.** Same-scaffold vs converted public trajectories, on the same 800 tasks.

RL is not part of the core study.

## 11. Limitations

See [docs/limitations.md](docs/limitations.md). In short:
- one model size, one harness and one 48-task panel, now heavily inspected;
- mostly single runs per arm;
- E6R is a 4-task pilot;
- no result here is statistically significant at conventional thresholds after accounting for the number of comparisons;
- the thinking-off vs thinking-on contrast is confounded;
- raw traces cannot be published.

## 12. Reproducibility

Published here:
- a sanitized preregistration summary per experiment, with the SHA-256 and freeze time of the withheld original;
- registered results and verdicts;
- anonymized per-task outcomes for every valid 48-task run;
- a standard-library script that recomputes every paired table, McNemar p-value and run-to-run flip count (`python analysis/verify_paired_stats.py`).
- the test-set inventory and mining-feasibility scripts (`analysis/post_release_inventory.py`, `analysis/post_release_mining_feasibility.py`), which recompute every test-set count from pinned dataset revisions and cached GitHub answers.

Not published: raw traces, task identifiers, prompts and harness-dependent code, because of redistribution terms ([DATA_AND_LICENSING.md](DATA_AND_LICENSING.md)). The proposed study uses openly licensed tasks (published datasets under CC-BY-4.0 or MIT, and tasks mined from repositories under OSI-approved licenses), so its full traces can be released.
