# Research plan: when does trajectory fine-tuning help a thinking coding agent?

*Status: planned. Nothing in this document has been run yet, except where it cites the preliminary experiments in [experiments/](experiments/README.md). This plan will be frozen, with SHA-256 manifests, phase by phase before each phase starts.*

**Claim labels:**
- **[FACT]**: a public source.
- **[LOCAL]**: a preliminary experiment in this repository.
- **[INFERENCE]**: my reasoning from those.
- **[HYPOTHESIS]**: to be tested.

## 1. Summary

The study measures the SFT data-scaling curve for Gemma 4 12B as a native-tool-calling, thinking-on repository agent:
- **Training data:** 200 to 1,600 execution-verified trajectories from a Gemma 4 31B teacher, recorded in exactly the scaffold used at test time.
- **Evaluation, in two tiers that are never pooled (§4.2):**
  - **Tier A (primary):** Python issues created on or after Gemma 4's release (2 Apr 2026), from repositories absent from training. Target: at least 200 gold-valid tasks. The realized size is frozen before training.
  - **Tier B (secondary):** tasks created after the January 2025 pretraining cutoff but before release, reported separately and never called post-release.
- **Seeds:** 3 training seeds per data size.

At a fixed size, two ablations ask:
1. whether the student must be trained on Gemma's native thought channel;
2. whether self-generated, same-scaffold data beats free public trajectories from a stronger open teacher on the same tasks.

A Phase 0 audit first verifies that the served adapter is the trained adapter. All results are released, including nulls.

## 2. Background

- **[FACT] CyberForge** (arXiv 2608.06471) is the only Gemma-specific agent-SFT scaling study.
  - Its 12B student, taught by Gemma 31B: 8.7% untrained → **3.6% at 220** trajectories → 12.1% at 440 → 16.0% at 880.
  - It ran one training seed, in a C/C++ vulnerability-repair domain with a sanitizer-crash oracle, using mini-swe-agent with one bash command per turn and visible text reasoning.
  - Reasoning handling, loss masking and scaffold were held fixed.
  - Seven training projects also appear in its in-domain test benchmark.
- **[FACT] Public SFT attempts on Gemma 4 repository agents mostly tied or lost.** These used own-agent, converted and teacher trajectories, often with data that did not match thinking-mode inference.
- **[FACT] Gemma 4 has specific training and serving traps.**
  - K=V global attention layers have no `v_proj`.
  - head_dim 512 on the global layers.
  - Runtime adapters have been reported to be ignored or under-applied in vLLM.
- **[LOCAL] Thinking fades when earlier thoughts are dropped from context** (E6R pilot: 47% vs 100% of calls).
- **[LOCAL] Remaining failures are competence, not protocol** (E3, E4). After tool-protocol fixes, the remaining failures were localization and fix quality.

**Gap.** No seeded Python-repository SFT scaling curve exists for any Gemma 4 size. No reasoning-retention ablation exists for thinking-on Gemma agents. No same-task comparison exists between same-scaffold and converted public trajectories.

## 3. Research questions and hypotheses

**RQ1 (primary): verified-trajectory scaling.** How many same-scaffold, execution-verified 31B-teacher trajectories does LoRA SFT need before Gemma 4 12B resolves more unseen, post-release Python issues (Tier A) than the untrained 12B in the same scaffold?
- **H1a [HYPOTHESIS]:** at N = 200, SFT is no better than the untrained model.
- **H1b [HYPOTHESIS]:** some N ≤ 1,600 gives a Holm-significant gain, and the gain at 1,600 is at least the gain at 800.
- **Falsification:** any of these outcomes is informative and will be published.
  - a significant gain already at 200;
  - no significant N;
  - a decline from 800 to 1,600.

**RQ2: reasoning retention.** With thinking on at inference, does it matter whether the training targets contain the teacher's native thoughts?
- **H2 [HYPOTHESIS]:** at N = 800, thoughts retained (arm R) resolve more tasks than thoughts stripped (arm S).
- **Mechanism check:** arm S shows thinking active on fewer calls (< 90%), against ≥ 90% in arm R. This is the training-time analogue of the E6R effect.

**RQ3: scaffold and data source.** On the same 800 tasks, does same-scaffold Gemma-teacher data beat resolved public trajectories from a stronger open teacher (Qwen3-Coder-480B in OpenHands), converted to our tool schema?
- **H3 [HYPOTHESIS]:** S beats C.
- The comparison uses S rather than R because the public trajectories have no Gemma thought channel, so this matches the reasoning condition.
- **Disclosed confound:** teacher identity and scaffold differ together. This answers the practical question "is generating my own data worth it?", not a pure scaffold-only question.

**Engineering gate (Phase 0, not a research claim).** Does vLLM runtime LoRA reproduce the merged adapter? If agreement is below threshold, every evaluation uses merged weights. See [phase0/adapter-serving-audit](phase0/adapter-serving-audit/README.md).

## 4. Design

### 4.1 Scaffold

One fixed, open re-implementation of a native Gemma 4 function-calling agent is used for all generation and evaluation:
- **Tools:** shell, read, edit, write, search, status, submit.
- **Thinking:** on, budget 4,096 tokens, thoughts kept within and across tool turns.
- **Context:** compaction at about 28K tokens in a 32K window.
- **Budgets: 40 tool calls and 48K generated tokens, with no wall-clock cap**, so outcomes do not depend on GPU contention. **[LOCAL]** E8 showed time caps binding on 9–10 of 48 tasks.
- **Sampling:** Gemma defaults (T 1.0, top-p 0.95, top-k 64).
- **Task environments:** each task runs in its own Docker image.

### 4.2 Data, splits and evaluation tiers

All splits are Python-only and frozen with SHA-256 manifests before any training. **No task is selected using any model's performance.**

**Decisions fixed on 27 Oct 2026, before any training or evaluation, from published counts only:**
1. **Remove the overlapping repositories from training, not from the test pool.** 14 repositories have published post-release tasks and also appear in the SWE-rebench-V2 Python pool. They are removed from every training use: teacher trajectory generation, the converted public trajectories of arm C, the LR pilot and validation. This costs 317 of 7,243 V2 Python tasks (4.4%); training repositories go from 690 to 676. In exchange, all 62 published post-release candidates stay available for Tier A ([inventory](analysis/post_release_task_inventory.md), option B).
2. **Exclude the development repositories from both tiers.** FastAPI, Rich, Requests and HTTPX were the repositories of the preliminary development pool, on which the scaffold and prompts were tuned.
3. **Evaluate in two tiers and report them separately.** Tier B is never merged into Tier A to form a larger primary benchmark.

| Split | Tasks created | Sources | Size | Use |
|---|---|---|---|---|
| **Tier A (primary)** | on or after 2 Apr 2026 (Gemma 4 release) | the 62 published post-release SWE-rebench candidates, plus tasks mined with open tooling from pull requests created from 13 May 2026 (after published coverage ends) up to the mining date | target **≥ 200** gold-valid, preferably about 250; realized N frozen before training | All primary analyses |
| **Tier B (secondary)** | 1 Feb 2025 to 1 Apr 2026: after the January 2025 pretraining cutoff, before release | published SWE-rebench sets (CC-BY-4.0) and SWE-bench-Live (MIT) | whatever passes the same criteria: 806 candidates in 311 repositories, about 708 expected after validation | Secondary, separately reported robustness analyses |
| Validation | any | SWE-rebench-V2 Python tasks from held-out repositories, which are then removed from training | 100 | LR pilot, smoke checks and the Phase 0 downstream check only |
| Training pool | any | SWE-rebench-V2 Python tasks with Docker images (CC-BY-4.0), minus the 14 repositories above and the validation repositories | 6,926 tasks in 676 repositories before the validation hold-out | Teacher trajectory generation |

**Tier A criteria (all required):**
- pull request created on or after 2026-04-02T00:00Z. The issue may be older; the subset whose issue is also post-release is reported as a sensitivity analysis;
- Python repository (at least 75% Python, the SWE-rebench rule) under an OSI-approved or public-domain license;
- a reproducible Docker environment with a working test command;
- repository absent from the training pool (after decision 1) and not a development repository;
- gold patch passes the fail-to-pass and pass-to-pass tests **twice**; the empty patch fails the fail-to-pass tests; flaky tests are removed, and a task with no stable fail-to-pass test is dropped;
- tests need no network, GPU or special hardware.

Mined tasks must also pass SWE-rebench's deterministic candidate filters: merged into the default branch; exactly one linked issue, in the same repository, closed, with more than 10 characters of description; 1–15 files changed; both tests and non-test Python code modified. SWE-rebench's LLM-assessed difficulty filter is **not** applied, because it is a model judgement. The 62 published tasks did pass that filter, so Tier A results are also broken down by source (published vs mined) as a descriptive check. The full mining rules are in [analysis/post_release_mining_plan.md](analysis/post_release_mining_plan.md). They are frozen, with hashes, before any model sees a Tier A task.

**Tier B criteria:** the same, except for the creation window. **Caveat, stated wherever Tier B results appear:** tasks created after the published pretraining cutoff are likely outside base pretraining, but possible later post-training exposure cannot be excluded. Tier B tasks in training-pool repositories are dropped; Tier B never causes further removals from training.

**Size rules:**
- The primary post-release set targets at least 200 gold-valid tasks. Its realized size will be frozen before training, and power and minimum-detectable-effect calculations will be recomputed from the realized N. **The date criterion will not be weakened to meet a desired sample size.**
- If Tier A ends up below 200, it is reported at its realized N with the recomputed power. Tier B does not substitute for it.
- A per-repository cap, fixed in the frozen mining specification, limits the influence of any single repository. Tasks above the cap are dropped by seeded random selection.

**Mining-feasibility stage (CPU and network only; runs before any training).** It enumerates eligible post-12-May pull requests, records licenses and every filter's attrition, estimates environment-build feasibility, counts repo-disjoint candidates and writes a reproducible candidate inventory. It uses no model. The first pass was run on 27 Oct 2026; its results, and what they do and do not establish, are in [analysis/post_release_mining_plan.md](analysis/post_release_mining_plan.md).

**Feasibility (27 Oct 2026, counts only):** 12,913 candidate pull requests pass the filters in repositories with a known working environment. Whether at least 200 become gold-valid tasks depends on a conversion rate that only building and validating them can measure. It needs about 1.3% with no per-repository cap and about 5.6% with a cap of 10; in the published window, a curated public task set included 1.8% of comparable candidates. A CPU-only pilot measures the rate before anything is frozen.

### 4.3 Trajectory generation

- **Teacher:** Gemma 4 31B-it, served in FP8. Phase 0 checks agreement with bf16.
- **Attempts:** up to 2 per task.
- **Acceptance:** at most one verified trajectory per task, for breadth. A trajectory is accepted only if:
  - the hidden tests pass;
  - no test files were modified;
  - no response was truncated.

  Malformed tool-call turns inside accepted trajectories stay in context but are masked from the loss.
- **Subsets:** nested, 200 ⊂ 400 ⊂ 800 ⊂ 1,600, drawn with one fixed data seed and stratified by repository.
- **Ablation set:** the RQ2/RQ3 arms share one 800-task set, chosen from training-pool tasks (after the §4.2 exclusions) that also have a converted public trajectory. The N = 800 scaling subset reuses it if the overlap allows. This rule is fixed in advance.

### 4.4 Training

- **Student:** Gemma 4 12B-it on a bf16 base, so there is no quantization mismatch with serving.
- **LoRA:**
  - r 32, α 64, dropout 0.05;
  - targets: q, k, o, gate, up and down on all language-model layers, plus `v_proj` on sliding layers only;
  - target modules enumerated from the live model, with counts asserted.
- **Optimizer:** AdamW, LR 1e-4, cosine schedule, warmup 0.03, weight decay 0, gradient clipping 1.0, 3 epochs, effective batch 16 sequences.
- **LR pilot:** {5e-5, 1e-4} at N = 400 on validation only, with one preregistered selection.
- **Sequences:** compaction segments, at most 32K tokens. Cross-entropy is chunked over the 262K vocabulary.
- **Loss:** on assistant tokens only, meaning thoughts and tool calls. System prompt, issue text, tool outputs, file contents and test logs stay in context but are masked.
  - **Arm S:** thought content is removed from targets and history; thinking stays enabled in the system turn.
  - **Arm C:** OpenHands actions are mapped to our tools. A trajectory with any unmappable step is dropped, and the conversion loss is reported.
- **Seeds:** training seeds {1, 2, 3}. The data seed is fixed, which is a stated limitation.

### 4.5 Phase 0: train/serve audit

- **Adapters:** deliberately detectable tiny adapters on 12B and 31B.
- **Serving paths:** Hugging Face reference, vLLM runtime LoRA, and merged weights; bf16, FP8 and the QAT W4A16 base.
- **Measures:** target-module counts, per-token KL, top-1 agreement, logit-shift preservation and serving throughput.
- **Downstream check:** one N = 800 checkpoint evaluated both runtime and merged on 100 validation tasks.

Preregistration: [phase0/adapter-serving-audit/PREREGISTRATION.md](phase0/adapter-serving-audit/PREREGISTRATION.md).

## 5. Evaluation and statistics

- **Primary metric:** resolved rate on the frozen Tier A set.
- **Primary analysis:** paired by task. For each N:
  - d_q = (mean over 3 SFT seeds of solved_q) − (mean over 3 untrained samples of solved_q);
  - exact sign-flip randomization test on the mean of d_q;
  - stratified bootstrap 95% CI over tasks.
  - Holm correction across the four N.
- **Secondary analysis:** R vs S and S vs C with the same procedure, Holm across the two. Per-seed exact McNemar tests are reported descriptively.
- **Definition:** N* is the smallest N with a Holm-adjusted significant gain.
- **Tier B:** the same analyses, reported separately as secondary results with the Tier B caveat. Tier B can add statistical precision, but it never enters a primary test and is never pooled with Tier A.
- **Power.** The primary post-release set targets at least 200 gold-valid tasks. Its realized size will be frozen before training, and power and minimum-detectable-effect calculations will be recomputed from the realized N and published with the frozen plan. They will use a simulation with heterogeneous per-task difficulty and seed-specific noise. The date criterion will not be weakened to meet a desired sample size. *(Earlier power figures assumed about 300 test tasks; they are withdrawn.)*
- **Secondary metrics:** thinking-active share; malformed-call rate; edit-then-verify rate; no-edit and no-submit rates; tokens per task; trajectory length.
- **Capability retention:** a LiveCodeBench subset and IFEval for untrained 12B against key checkpoints.
- **Reference:** untrained 31B with 2 samples per task.
- **Analysis code:** frozen before any test-set evaluation and validated on stand-in data first, as in E7 and E8.

## 6. Stopping rules and failure handling (preregistered)

| Condition | Action |
|---|---|
| Phase 0 agreement below the gate | Evaluate merged weights only; publish the shortfall |
| Teacher yield < 15% per attempt after 1,000 attempts | Cap the top N at 800; test set and analysis unchanged |
| Mining-feasibility stage shows that 200 gold-valid Tier A tasks are not attainable | Decide before training, from counts only, whether to proceed at the realized N; publish the decision and the recomputed power |
| Tier A below 200 after gold validation | Report Tier A at its realized N with recomputed power; never relax the post-release date, repo-disjointness or validation rules; Tier B stays secondary |
| Training throughput ≥ 2× worse than planned | Drop the third seed at N = 200 only |
| No N gives a significant gain | Publish the negative curve with behavioural diagnostics |
| Damage to general coding ability | Report it as a finding |
| 31B confirmation and RL-readiness sampling | Only if H1b holds; not part of the core study |

**Reinforcement learning.** No GRPO, RLVR or DAPO training is in the core study.
- **[FACT]** 31B is a low-entropy policy: in one study only 1–15 of 192 GRPO groups per step had reward variance.
- **[FACT]** Every public software-engineering RL recipe starts from an SFT or RFT checkpoint.

If SFT works, the first RL step is measurement only: sample k = 8 rollouts on held-out training tasks from the untrained and SFT models, and report the share of tasks with mixed outcomes, zero-variance groups, entropy and length.

## 7. Estimated compute requirements

**Planning rates** [INFERENCE]:
- 31B agent attempt: 1.5 H100-minutes.
- 12B attempt: 0.75 H100-minutes.
- 12B LoRA: 18 H100-hours per 1,000 trajectories (about 30K tokens each, 3 epochs).
- 31B LoRA: 40 H100-hours per 1,000 trajectories.

**Anchors:**
- **[LOCAL]** About 28 model calls, about 9.6K generated tokens and about 15K peak context per task, from the E8 call logs.
- **[FACT]** CyberForge's Gemma teacher needed about 6.6 GPU-minutes per accepted trajectory. This plan assumes 5.0.

Phase 0 measures the real throughput before the plan proceeds.

| Scope | Contents | H100-hours |
|---|---|---:|
| Minimum | N ≤ 800 × 2 seeds; reasoning ablation; two-tier test set (sizes frozen before training) | ≈ 250 |
| **Core** | N ≤ 1,600 × 3 seeds; RQ2 and RQ3 arms; LR pilot; 31B reference | **≈ 580** |
| Extended | Core, plus 31B LoRA confirmation (2 seeds) and RL-readiness sampling | ≈ 810 |

| Core breakdown | H100-hours |
|---|---:|
| Teacher trajectory generation (~5,800 attempts → ~1,750 verified) | 145 |
| 12B training (12 scaling runs, 6 ablation runs, 2-run LR pilot) | 258 |
| Evaluation (~7,400 agent episodes plus retention checks) | 106 |
| Phase 0 audit and calibration | 18 |
| Contingency | 53 |

**Evaluation sizing [INFERENCE].** The evaluation line was sized for about 300 test tasks. From the planning rates above, evaluating every checkpoint (21 12B evaluations plus 2 31B reference samples per task) costs about 31 H100-hours per 100 test tasks. The final evaluation budget is fixed when the Tier A and Tier B sizes are frozen. Task mining, environment builds and gold validation run on CPUs and are not counted as GPU hours.

Data generation dominates the cost of the knowledge this study produces. Training is many small runs, because seeds are the point. Evaluation is large because 48-task panels proved too noisy.

## 8. Public outputs

**Committed, regardless of outcome:**
- a technical report;
- code under Apache-2.0: scaffold, training and evaluation configs, statistics, adapter-consistency test suite;
- split ID lists and hashes, candidate inventories and the mining code;
- verified Gemma 4 31B trajectories on openly licensed tasks, subject to the Gemma terms;
- LoRA adapters;
- per-task outcomes for every checkpoint;
- frozen preregistrations.

**Conditional:** an arXiv preprint (requires an endorsement as a first-time submitter); a workshop submission if the results warrant it. No acceptance is assumed.

## 9. Milestones

| Weeks from start | Milestone |
|---|---|
| 0–2 (before training) | Tier A mining, environment builds and gold validation (CPU); Phase 0 report and test suite; throughput measured; Tier A, Tier B, validation and training splits frozen |
| 3–5 | ≥ 1,600 verified trajectories; yield and cost report |
| 5–8 | 12 scaling runs trained and evaluated; primary analysis run unchanged |
| 8–10 | R / S / C ablations evaluated; interim write-up |
| 10–12 | Report, code, data and adapters released |
