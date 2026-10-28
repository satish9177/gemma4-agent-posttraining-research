# Phase 0 preregistration (DRAFT v0, not frozen)

**Status:** drafted 2026-10-27. It will be frozen with a SHA-256 manifest of this file, `METRICS.md`, `config.yaml` and the audit code immediately before the first GPU run. Any later change requires a separately frozen amendment. **Not run.**

## 1. Question

Does vLLM runtime LoRA apply a trained Gemma 4 LoRA adapter faithfully, compared with a Hugging Face/PEFT reference and with merged weights?

## 2. Models and stages

- **Stage A** (low cost, first): Gemma 4 12B-it, bf16. If GPU memory forces it, E4B-it is used instead and the reason is recorded.
- **Stage B** (before any 31B work): Gemma 4 31B-it, bf16.

Model revisions are pinned by Hugging Face commit hash in the frozen config.

## 3. Adapters (trained for this audit only)

| Adapter | Purpose | Recipe (planned) |
|---|---|---|
| **A1 "marker"** | A large, unambiguous effect, used to detect no-op or partial application | LoRA r 8, α 16. About 200 steps on synthetic prompts whose target response starts with a fixed marker string. |
| **A2 "diffuse"** | A small, distributed logit shift across all targeted modules, used to detect under-application | LoRA r 32, α 64. About 200 steps of low-LR SFT on openly licensed instruction data. |
| **A3 "naive targets"** | Shows silent module skipping | A2's recipe, with plain name targets including `v_proj` everywhere |

**Targets for A1 and A2:** q, k, o, gate, up and down projections on every language-model layer, plus `v_proj` only on layers that have one. Modules are enumerated from the instantiated model, not from name patterns. Vision and audio towers are excluded.

## 4. Serving paths

- **P1** HF + PEFT, unmerged: the reference.
- **P2** HF, merged.
- **P3** vLLM runtime LoRA.
- **P4** vLLM, merged weights.
- **Descriptive only:** P5, vLLM runtime LoRA on an FP8 base; P6, vLLM runtime LoRA on the QAT W4A16 base.

All bf16 paths use the same tokenizer, chat template, and prompts.

## 5. Prompts

500 fixed prompts, frozen as a JSONL file with SHA-256:
- 250 general instruction prompts;
- 250 agent-format prompts. These have a system turn with thinking enabled, a tool schema, and 1–3 prior tool-call turns built from **openly licensed** repository issues.

Every prompt has a fixed continuation of 64 tokens, used for teacher-forced scoring.

## 6. Metrics and pass criteria

Full definitions are in [METRICS.md](METRICS.md).

| ID | Metric | Pass (bf16 paths P2–P4 vs P1) |
|---|---|---|
| M1 | Target-module count | Equals the count expected from the model config, for training, P1 and P3, and is logged by vLLM. For A3, the number of skipped `v_proj` targets is reported. |
| M2 | Adapter-effect retention ρ | Median ρ in [0.95, 1.05] for A1 and A2 |
| M3 | Top-1 agreement, teacher-forced | ≥ 99.0% |
| M4 | Per-token KL to P1, top-20 support | Median ≤ 0.01 nats, reported with p99 |
| M5 | Greedy (T = 0) exact match on 50 prompts × 128 tokens | Reported; the gate is set by M2–M4, because kernels may be nondeterministic |
| M6 | Adapter separation | The A1 marker appears in ≥ 95% of greedy outputs on every path; KL(base ‖ adapter) ≥ 10× the M4 noise level |
| M7 | Throughput | Decode tokens/s at batch sizes 1 and 16, runtime LoRA vs merged; reported, no gate |

## 7. Decision rule

- **PASS:** P3 meets M1–M4 and M6 for both A1 and A2. The post-training study may evaluate with runtime LoRA.
- **FAIL:** every study evaluation uses merged weights (P4). The failure, with its measured ρ and KL, is published as a result and, where appropriate, reported upstream.
- **Merge check failure:** if P2 or P4 fails against P1, Phase 0 stops. Merging itself is wrong, and no study run starts until it is fixed.

## 8. Recorded environment

GPU model and driver, CUDA, torch, transformers, PEFT and vLLM versions, model and adapter hashes, and the prompt-file hash.

## 9. What this audit does not claim

It does not measure task performance, and it does not show that any adapter improves Gemma 4. A PASS means only that serving matched training for these adapters, on this stack.
