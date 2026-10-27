# When does trajectory fine-tuning help a thinking coding agent?

**Data scale, reasoning retention and scaffold match for Gemma 4 on unseen Python repositories**

This is an independent research record on Gemma 4 as a repository-level coding agent. It contains:
- preregistered preliminary experiments on thinking behaviour, tool-protocol reliability and inference budgets;
- every registered verdict, including null, negative and invalid runs;
- the plan for a seeded post-training study that follows from them.

Author: Satish Kommanaboina, independent researcher. Status: preliminary study complete (E9 has run but is not yet analysed); the post-training study is planned.

---

## 1. Research question

> For Gemma 4 12B running as a native-tool-calling, thinking-on repository agent, how many same-scaffold, execution-verified trajectories does LoRA SFT need before it *improves*, rather than degrades, resolution of unseen, post-release Python issues? Does it matter whether training keeps Gemma's native reasoning channel, and whether the data come from the same scaffold?

The full design is in [RESEARCH_PLAN.md](RESEARCH_PLAN.md).

## 2. Why this exists

- **Public fine-tuning results are mostly negative.** Public attempts to fine-tune Gemma 4 into a better repository-level coding agent have mostly tied or lost against the untrained model. The reported causes are rarely model capacity: too few trajectories, data recorded in a different agent scaffold, reasoning formats that do not match thinking-mode inference, and tiny evaluations. See [docs/evidence-map.md](docs/evidence-map.md).
- **The one controlled positive result has gaps.** CyberForge (arXiv 2608.06471) found that SFT made Gemma 4 12B *worse* at 220 verified trajectories and better at 440–880. But it studies C/C++ security patching in a text-protocol scaffold, uses one training seed and does not vary how reasoning is handled.
- **Gemma 4 thinks in a separate channel.** Google's formatting guide says earlier thoughts must stay in the history between tool calls. Our pilot (E6R) found that removing them makes thinking fade. Whether the same happens when thoughts are removed from *training* data is untested.
- **Train/serve LoRA consistency is a known confound.** Adapters have been reported to load in vLLM with no effect, or with only part of their effect, and a `v_proj` target silently skips Gemma 4's global attention layers. Many published "LoRA did nothing" results cannot be interpreted until serving is verified.

## 3. Preliminary findings

All runs used Gemma 4 31B (QAT W4A16) served by vLLM on 4× NVIDIA L4, on a fixed 48-task development panel of Python repository issues. Every experiment was preregistered and hash-frozen before its GPU run. Numbers below are the registered results. They are **not** evidence of statistical significance unless stated, and none is.

| Finding | Evidence | Caveat |
|---|---|---|
| **Earlier thoughts must stay in context.** When previous thoughts were dropped from the history, thinking was active on **47%** of calls (48/103), against **100%** (77/77) when they were kept. Malformed tool calls were 6/99 vs 0/75. | [E6R](experiments/e6r/RESULTS.md) | **Small mechanical pilot: 4 tasks per arm.** It measures behaviour, not solve rate. |
| **Fixing the tool protocol removed errors, but not competence failures.** Read-serialization guidance cut corrupted tool calls from 19.6% to 6.4%; solves went 12 → 15/48, registered *CONFIRMED* at exactly the +3 threshold. A second protocol change eliminated edit-argument corruption (83 calls → 0), yet solves stayed at 13 vs 14 (*TIE*). The remaining failures were wrong localization and wrong fixes. | [E3](experiments/e3/RESULTS.md), [E4](experiments/e4/RESULTS.md) | Thinking off; one 48-task panel |
| **A strong inference-only baseline exists.** Reproducing a public thinking-on configuration solved **19/48**. | [E7](experiments/e7/RESULTS.md) | Registered verdict *NOT PROMISING*. Its criterion was later found to be flawed; the verdict is kept unchanged. |
| **The tool-budget effect is small and not significant.** Paired 28 vs 36 tool calls: **21/48 → 24/48**. Three tasks were solved only by the 36-call arm and none only by the 28-call arm; exact McNemar **p ≈ 0.25**. Registered verdicts: competitive **WIN**; mechanism (budget relief) **NOT CONFIRMED**. | [E8](experiments/e8/RESULTS.md) | Not significant. An external run of the 36-call setting later exceeded its aggregate runtime budget twice. |
| **Run-to-run noise is measured.** Byte-identical configurations flipped **2–4 of 48** tasks between runs, and solved counts moved by up to 2. | [results/](results/README.md) | Differences of about 3 tasks or fewer on 48 tasks are within noise. |

**The narrative these results support.**
1. Gemma 4's thinking needs its history.
2. Once the scaffold was made reliable and the baseline strong, the remaining failures were competence failures: localization and fix quality.
3. Inference-time levers then produced only small, noisy gains.
4. That points to weight-level post-training, but only with enough verified data, the right reasoning format and a verified serving path.

The longer write-up is the [technical note](TECHNICAL_NOTE.md).

## 4. Research principles

- **Preregistration before every GPU run.** Question, arms, validity gates and decision rules are written down first.
- **SHA-256 freezing** of every file a run depends on, before launch, and verification afterwards.
- **Paired designs.** Both arms run on the same tasks, served by one inference server, one job at a time, with arm order alternating by task.
- **In-run validity gates**, including a check that the manipulation actually took effect.
- **Invalid runs are archived, labelled and excluded.** No verdict is computed from partial data.
- **Negative and null results are kept** with the same prominence as positive ones.
- **Registered verdicts are never rewritten** after seeing the data. Post-hoc analysis is labelled as such.

Details: [docs/methodology.md](docs/methodology.md).

## 5. Next research phase (planned, not yet run)

1. **Phase 0 — adapter train/serve audit.** Does vLLM runtime LoRA apply the adapter we trained? It compares a Hugging Face reference, runtime LoRA and merged weights. See [phase0/adapter-serving-audit](phase0/adapter-serving-audit/README.md). *Planned; no result yet.*
2. **Fresh evaluation set.** Python tasks created after Gemma 4's release (2 Apr 2026), from repositories disjoint from training, with gold patches validated twice. **Feasibility check:** only 62 such tasks are published (47 repo-disjoint, about 41 expected to validate), far below the ~300 planned. The test set is being redesigned (task mining, training-pool exclusions, or a separately reported post-cutoff tier) **without relaxing the post-release date**. See [analysis/post_release_task_inventory.md](analysis/post_release_task_inventory.md).
3. **RQ1: scaling.** 12B LoRA SFT on 200 / 400 / 800 / 1,600 execution-verified Gemma 4 31B trajectories from the same scaffold, as nested subsets, with 3 training seeds each.
4. **RQ2: reasoning retention.** Native thoughts kept vs stripped from the training targets, with inference always thinking.
5. **RQ3: data source.** Same-scaffold trajectories vs public trajectories from a stronger open teacher, converted to the same tool format, on the same tasks.

**Reinforcement learning is not part of the core study.** RL is considered only if SFT produces a reliable held-out gain. Even then, the first step is to *measure* whether there is enough reward variance for GRPO to learn from.

## 6. Repository map

| Path | Contents |
|---|---|
| [RESEARCH_PLAN.md](RESEARCH_PLAN.md) | Research questions, hypotheses, design, statistics, stopping rules, compute estimate |
| [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md) | What the preregistered experiments taught us about Gemma 4 as a coding agent |
| [experiments/](experiments/README.md) | One folder per experiment (E3–E9): sanitized preregistration, results, metadata |
| [results/](results/README.md) | Aggregate results and anonymized per-task outcomes |
| [analysis/](analysis/) | Statistics verification script; post-release task inventory |
| [phase0/adapter-serving-audit/](phase0/adapter-serving-audit/README.md) | Preregistration and metrics for the planned train/serve audit |
| [scripts/](scripts/) | Generic tooling (SHA-256 freeze manifests) |
| [docs/methodology.md](docs/methodology.md) | How experiments are designed, frozen, validated and reported |
| [docs/evidence-map.md](docs/evidence-map.md) | Summary of public Gemma 4 post-training evidence, with sources |
| [docs/limitations.md](docs/limitations.md) | Known limitations of the preliminary study |
| [DATA_AND_LICENSING.md](DATA_AND_LICENSING.md) | What is and is not published, and why |
| [PUBLICATION_AUDIT.md](PUBLICATION_AUDIT.md) | Pre-publication checklist for claims, data and secrets |

Reproduce the paired statistics: `python analysis/verify_paired_stats.py` (standard library only).

## 7. Data and licensing

Some preliminary evaluations used benchmark assets whose terms restrict redistribution. Raw task data, task identifiers, gold patches, agent traces, prompts and harness-dependent code are therefore **not** included. This repository publishes:
- sanitized preregistration summaries, with the SHA-256 of each withheld original;
- aggregate measurements;
- anonymized per-task outcomes;
- new, generic analysis code.

Details are in [DATA_AND_LICENSING.md](DATA_AND_LICENSING.md). The future study uses only openly licensed task sources (CC-BY-4.0 or MIT), so its data and traces can be released.

Code: Apache-2.0 ([LICENSE](LICENSE)). Documentation and result tables: CC BY 4.0. Citation: [CITATION.cff](CITATION.cff).
