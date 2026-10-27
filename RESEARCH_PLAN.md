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
- **Test set:** Python issues created after Gemma 4's release, from repositories unseen in training. The target was about 300, but a feasibility check found far fewer published candidates (§4.2), so the test-set design is being revised.
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

**RQ1 (primary): verified-trajectory scaling.** How many same-scaffold, execution-verified 31B-teacher trajectories does LoRA SFT need before Gemma 4 12B resolves more unseen, post-release Python issues than the untrained 12B in the same scaffold?
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

### 4.2 Data and splits

All splits are Python-only, repo-disjoint, and frozen with hashes before any training.

| Split | Source | Size | Use |
|---|---|---|---|
| Test | Tasks created **on or after 2 Apr 2026** (Gemma 4 release; pretraining cutoff Jan 2025), from SWE-rebench monthly splits (CC-BY-4.0), topped up from SWE-bench-Live (MIT) if needed | target 300, minimum 200 | Primary evaluation only |
| Validation | Same sources, repo-disjoint from test | 100 | LR pilot and smoke checks only |
| Training pool | SWE-rebench-V2 Python tasks with Docker images (CC-BY-4.0) | about 4,000 | Teacher trajectory generation |

- **Gold validation:** the gold patch must pass the fail-to-pass and pass-to-pass tests **twice**, and the empty patch must fail. Flaky tasks are dropped. Exclusions happen before freezing, never after.
- **Date criterion:** fixed. If fewer than 200 valid tasks exist, the set is not padded with older tasks; the shortfall is reported.
- **Feasibility check (27 Oct 2026): the target is NOT reachable from published data.** Only **62** Python tasks created on or after 2 Apr 2026 have a published Docker image and an open license. That drops to **47** after removing repositories that also appear in the training pool, and to an estimated **~41** after gold validation (rough prior: 88% survival). Published post-release data currently stop at 12 May 2026. Details: [analysis/post_release_task_inventory.md](analysis/post_release_task_inventory.md).
- **The date criterion is not relaxed to reach a target.** Before any training, the test set will be redesigned and frozen using one or more of these options, each disclosed:
  1. mine additional post-release tasks with the open SWE-rebench collection pipeline, from repositories disjoint from training;
  2. remove the 14 overlapping repositories from the *training* pool instead (−317 of 7,243 tasks), keeping all 62 post-release tasks for testing;
  3. add a clearly separated, larger *secondary* tier of tasks created after the January 2025 pretraining cutoff but before release, reported apart from the post-release tier because post-training contamination cannot be excluded;
  4. wait for further monthly releases.

  The power figures in §5 assume about 300 tasks and will be recomputed for the final design.

### 4.3 Trajectory generation

- **Teacher:** Gemma 4 31B-it, served in FP8. Phase 0 checks agreement with bf16.
- **Attempts:** up to 2 per task.
- **Acceptance:** at most one verified trajectory per task, for breadth. A trajectory is accepted only if:
  - the hidden tests pass;
  - no test files were modified;
  - no response was truncated.

  Malformed tool-call turns inside accepted trajectories stay in context but are masked from the loss.
- **Subsets:** nested, 200 ⊂ 400 ⊂ 800 ⊂ 1,600, drawn with one fixed data seed and stratified by repository.
- **Ablation set:** the RQ2/RQ3 arms share one 800-task set, chosen from tasks that also have a converted public trajectory. The N = 800 scaling subset reuses it if the overlap allows. This rule is fixed in advance.

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

- **Primary metric:** resolved rate on the frozen test set.
- **Primary analysis:** paired by task. For each N:
  - d_q = (mean over 3 SFT seeds of solved_q) − (mean over 3 untrained samples of solved_q);
  - exact sign-flip randomization test on the mean of d_q;
  - stratified bootstrap 95% CI over tasks.
  - Holm correction across the four N.
- **Secondary analysis:** R vs S and S vs C with the same procedure, Holm across the two. Per-seed exact McNemar tests are reported descriptively.
- **Definition:** N* is the smallest N with a Holm-adjusted significant gain.
- **Power [INFERENCE], by simulation** with heterogeneous per-task difficulty and seed-specific noise:
  - with 300 tasks and 3 vs 3: about 80% at +5–6 points (α = 0.0125), and ≥ 90% at +7, CyberForge's 12B gain;
  - with 200 tasks: about 80% at roughly +7.
- **Secondary metrics:** thinking-active share; malformed-call rate; edit-then-verify rate; no-edit and no-submit rates; tokens per task; trajectory length.
- **Capability retention:** a LiveCodeBench subset and IFEval for untrained 12B against key checkpoints.
- **Reference:** untrained 31B with 2 samples per task.
- **Analysis code:** frozen before any test-set evaluation and validated on stand-in data first, as in E7 and E8.

## 6. Stopping rules and failure handling (preregistered)

| Condition | Action |
|---|---|
| Phase 0 agreement below the gate | Evaluate merged weights only; publish the shortfall |
| Teacher yield < 15% per attempt after 1,000 attempts | Cap the top N at 800; test set and analysis unchanged |
| Fewer valid post-release test tasks than planned (already the case; see §4.2) | Redesign per §4.2 options before training and report the power; never relax the post-release date or repo-disjointness for the primary tier |
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
| Minimum | N ≤ 800 × 2 seeds; reasoning ablation; ~300-task test (size under revision) | ≈ 250 |
| **Core** | N ≤ 1,600 × 3 seeds; RQ2 and RQ3 arms; LR pilot; 31B reference | **≈ 580** |
| Extended | Core, plus 31B LoRA confirmation (2 seeds) and RL-readiness sampling | ≈ 810 |

| Core breakdown | H100-hours |
|---|---:|
| Teacher trajectory generation (~5,800 attempts → ~1,750 verified) | 145 |
| 12B training (12 scaling runs, 6 ablation runs, 2-run LR pilot) | 258 |
| Evaluation (~7,400 agent episodes plus retention checks) | 106 |
| Phase 0 audit and calibration | 18 |
| Contingency | 53 |

Data generation dominates the cost of the knowledge this study produces. Training is many small runs, because seeds are the point. Evaluation is large because 48-task panels proved too noisy.

## 8. Public outputs

**Committed, regardless of outcome:**
- a technical report;
- code under Apache-2.0: scaffold, training and evaluation configs, statistics, adapter-consistency test suite;
- split ID lists and hashes;
- verified Gemma 4 31B trajectories on openly licensed tasks, subject to the Gemma terms;
- LoRA adapters;
- per-task outcomes for every checkpoint;
- frozen preregistrations.

**Conditional:** an arXiv preprint (requires an endorsement as a first-time submitter); a workshop submission if the results warrant it. No acceptance is assumed.

## 9. Milestones

| Weeks from start | Milestone |
|---|---|
| 1–2 | Phase 0 report and test suite; throughput measured; test, validation and training splits frozen |
| 3–5 | ≥ 1,600 verified trajectories; yield and cost report |
| 5–8 | 12 scaling runs trained and evaluated; primary analysis run unchanged |
| 8–10 | R / S / C ablations evaluated; interim write-up |
| 10–12 | Report, code, data and adapters released |
