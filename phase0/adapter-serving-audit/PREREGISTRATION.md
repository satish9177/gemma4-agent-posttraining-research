# Phase 0 preregistration (v1, Stage A)

**Status:** v1, written 2026-10-28. It replaces the unfrozen draft v0. This file, `METRICS.md`, `config.yaml`,
`build_prompts.py`, `audit_modal.py`, `preflight_modal.py`, `analyze_audit.py`, `prompts_summary.json`,
`PREFLIGHT.json` and the three data files are frozen with SHA-256 (`FREEZE.json`) before the first GPU step. Any later change needs a separately frozen
amendment.

**Purpose (engineering gate, not a benchmark experiment):** show that we can train a Gemma 4 adapter correctly, and
measure whether the serving stack applies it faithfully.

## 1. Question

Does vLLM runtime LoRA apply a trained Gemma 4 LoRA adapter faithfully? The crucial comparison is the **base → adapter
effect** under runtime LoRA versus the same effect under merged weights and under the Hugging Face/PEFT reference. A
simple output match is not the test.

## 2. Scope of this run

- **Stage A only:** `google/gemma-4-12B-it`, revision `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` (Apache-2.0, not
  gated), bf16.
- **Deferred:**
  - Stage B (31B), which must run before any 31B study work;
  - the descriptive FP8 path (P5) and QAT W4A16 path (P6).
- **Pinned stack:** vLLM 0.32.0, torch 2.13.0, transformers 5.19.0, PEFT 0.21.2, accelerate 1.15.0, Python 3.12.
  - The CUDA runtime is whatever torch 2.13.0's wheels ship with; GPU and driver are recorded at run time.
- **Compute:** Modal, one NVIDIA A100-80GB per GPU step.
  - Price: Modal's list price is $2.50 per GPU-hour (`modal billing rates`, 28 Oct 2026), plus CPU and memory.
  - Expected use: about 2–3 GPU-hours, about $6–8.
  - Cap: per-step timeouts (training 2 h, HF scoring 3 h, vLLM runtime LoRA 1.5 h, vLLM merged 1 h each) limit the
    worst case to 8.5 GPU-hours, about $21 of GPU time. That is inside Modal's $30 monthly free credit.
  - The run is paid from Modal's free monthly credit. Each step's wall time is logged (`out/timing.jsonl`); the billed cost is read from
    `modal billing` afterwards.
- **Model access:** the pinned revision is public and not gated. It is downloaded anonymously; no Hugging Face token
  or Modal secret is used.

## 2a. Pre-freeze checks and changes (disclosed)

- **CPU-only preflight**, run before the freeze. The code is `_preflight_impl()` in `audit_modal.py`. It runs
  through `preflight_modal.py`, a separate app that declares no GPU, because Modal will not create an app that
  declares GPU functions in a workspace without a payment method. The preflight:
  - downloaded the pinned model and recorded every package version in the built image;
  - checked the vLLM API the audit uses;
  - enumerated the LoRA targets and tried PEFT wrapping on a meta-device model;
  - measured rendered prompt lengths and usable training examples.

  It ran no forward pass and produced no model output. Its output is `PREFLIGHT.json`.
- **Engineering changes** made after v1 was written and before the freeze. None touches a threshold, metric, adapter
  recipe or prompt.
  - The steps are orchestrated by a Modal function, so the run does not depend on the local client.
  - The per-step timeouts above were lowered to cap cost.
  - vLLM `gpu_memory_utilization` went from 0.85 to 0.80, leaving room for full-vocabulary prompt log-probs.
  - The merged checkpoint no longer receives the base model's weight-index file.
  - If vLLM cannot start with LoRA enabled, the error is recorded (G1 fails) and the vLLM base is still measured.
  - The G1 code now also checks the PEFT-wrapped count, and that no vision or audio module carries LoRA, as G1 below
    states.

  The synthetic gate tests were re-run after these changes.

## 3. Model facts the audit checks

From the pinned config:
- 48 text layers; 8 are full-attention ("global") layers (every sixth);
- `attention_k_eq_v = true`, so global layers have no `v_proj`;
- head_dim 256 on sliding layers and 512 on global layers.

The **expected LoRA target count** is 48 × 6 (q, k, o, gate, up, down) + 40 `v_proj` (sliding layers only) = **328**.
The count is also enumerated from the instantiated model, and the two must agree.

## 4. Adapters (trained for this audit only)

| Adapter | Purpose | Recipe |
|---|---|---|
| **A1 "marker"** | A large, unambiguous effect, used to detect no-op or partial application | LoRA r 8, α 16, dropout 0. 200 steps, batch 8, LR 2e-4 (10-step warmup), on 1,600 Dolly prompts whose target response starts with `ZQX-AUDIT-MARKER`. |
| **A2 "diffuse"** | A smaller, distributed shift across all targets, used to detect under-application | LoRA r 32, α 64, dropout 0.05. 200 steps, batch 8, LR 5e-5, on 1,600 other Dolly prompt–response pairs. |
| **A3 "naive targets"** | Shows silent skipping and inappropriate targeting | A2's recipe with plain name targets (`q_proj` … `down_proj`, including `v_proj`), trained 20 steps. Used for module counts and for whether vLLM loads it. Not part of the gate. |

- **A1 and A2 targets:** the 328 language-model modules enumerated from the live model, as full module names. Vision
  and audio towers are excluded by construction.
- **Loss** is on response tokens only. AdamW, gradient clipping at 1.0, seed 20261027.
- **Changed from draft v0:** A1's learning rate (1e-4 → 2e-4) and A2's (2e-5 → 5e-5) were raised before any run. This
  ensures the adapters' effects sit well above serving noise; a separation check (G4) verifies it.

## 5. Prompts and scoring

- **500 frozen prompts** (`build_prompts.py`, seed 20261027):
  - 250 general prompts from `databricks/databricks-dolly-15k` @ `bdd27f4d` (CC BY-SA 3.0);
  - 250 agent-format prompts: a thinking-enabled system turn, a 4-tool schema, an issue text from
    `SWE-bench-Live/SWE-bench-Live` @ `b51a8642` (MIT), and 1–3 prior tool-call turns with earlier reasoning preserved.
  - No restricted benchmark content is used. The training subsets are disjoint from the evaluation prompts.
- **Fixed continuations:** the base model's greedy continuation of each prompt, up to 64 tokens (cut after the first
  end-of-turn token), generated once with Hugging Face.
- **Teacher-forced scoring:** every path scores those same tokens. Recorded per position: the token's log-prob, the
  top-20 token ids and their log-probs.
- **Engines:** Hugging Face scores one sequence at a time (no padding). vLLM uses `prompt_logprobs = 20` with prefix
  caching off.

## 6. Paths and decision rule

| Path | Engine |
|---|---|
| HF base / **P1** HF + PEFT unmerged (reference) / **P2** HF merged | transformers |
| vLLM base / **P3** vLLM runtime LoRA / **P4** vLLM merged weights | vLLM |

**Effect retention ρ** (M2) = Δ_variant / Δ_reference per token, where Δ = log p(adapter path) − log p(base on the same
engine). It is computed on tokens with |Δ_reference| ≥ 0.1 nats.

Because base-model numerics differ across engines, M3 and M4 thresholds are applied where the kernels match: P2 vs P1,
and P3 vs P4. Cross-engine values (P3 and P4 vs P1) are reported against the measured **engine noise floor** (HF base vs
vLLM base).

| Criterion | Pass condition (A1 and A2) |
|---|---|
| **G1 modules** | Enumerated targets = 328 = config-derived count. PEFT-wrapped and saved LoRA modules = 328 for each adapter, all in the language model (none in the vision or audio towers). vLLM starts with LoRA enabled and loads each adapter without error. |
| **G2 retention** | median ρ(P3 vs P1) ∈ [0.95, 1.05] **and** median ρ(P3 vs P4) ∈ [0.95, 1.05] |
| **G3 agreement** | within vLLM, P3 vs P4: top-1 agreement ≥ 99.0% and median KL(P4 ‖ P3) ≤ 0.01 nats |
| **G4 separation** | A1 marker in ≥ 95% of greedy outputs (50 general prompts, 128 tokens) on P1, P3 and P4; for A1 and A2, median KL(vLLM base ‖ P3) ≥ 10 × median KL(P4 ‖ P3) |
| **Merge check** | P2 vs P1: median ρ ∈ [0.95, 1.05], top-1 ≥ 99.0%, median KL ≤ 0.01 |

**Serving gate:**
- **PASS** if G1–G4 all hold. Runtime LoRA may then be used for evaluation.
- **FAIL** otherwise. Every later evaluation then uses merged weights (P4), and the failure is published with its
  measured ρ, top-1 and KL.
- **MERGE FAIL** if the merge check fails. No study run starts until merging is fixed.

The code is `analyze_audit.py`. It was tested on synthetic data before freezing:
- a faithful adapter gives PASS;
- an adapter applied at 80% gives FAIL (median ρ ≈ 0.73–0.79, depending on the synthetic setup);
- a LoRA module in the vision tower, a short PEFT-wrapped count, and a vLLM LoRA start failure each give FAIL through G1.

**Also reported (no gate):**
- greedy exact-match against HF merged (M5);
- the magnitude of each adapter's effect;
- vLLM's LoRA-wrapped module classes;
- A3's per-component counts (language, vision, audio) and the number of global layers where `v_proj` was requested
  but absent;
- decode throughput at batch 1 and 16 for the base model, runtime LoRA and merged weights (M7).

## 7. What this audit does not claim

It does not measure task performance or show that any adapter improves Gemma 4. A PASS means only that serving matched
training, for these adapters, on this pinned stack, at 12B.
