# Phase 0 metric definitions (planned)

## Notation

- P1 is the reference path (Hugging Face + PEFT, unmerged).
- B is the same model without the adapter, on the same path.
- Scores are teacher-forced: for prompt x and fixed continuation tokens y_1..y_T, log p(y_t | x, y_<t) is computed under each path.

## M1: target-module count

- **Expected:** the count enumerated from the instantiated model (layers × projections present on each layer). Global layers without `v_proj` are counted correctly.
- **Observed:** the modules with LoRA weights in the saved adapter, the modules wrapped by PEFT at load time, and the modules vLLM reports as LoRA-enabled.
- **Pass:** all observed counts equal the expected count.
- **For the naive-target adapter (A3):** the number of requested-but-absent targets is reported.

## M2: adapter-effect retention ρ (logit-shift preservation)

For each scored token: Δ_path(t) = log p_path(y_t) − log p_B(y_t).

ρ(t) = Δ_variant(t) / Δ_P1(t). It is computed only on tokens where |Δ_P1(t)| ≥ 0.1 nats, so that numerical noise does not dominate.

Report the median, IQR and the share of tokens with ρ < 0.9. Pass: median ρ ∈ [0.95, 1.05].

This metric detects partial application, such as the 75–80% retention reported publicly.

## M3: top-1 agreement

The share of positions where the argmax token under the variant equals the argmax under P1, teacher-forced. Pass ≥ 99.0% for bf16 paths.

## M4: per-token KL

KL(P1 ‖ variant) is computed at each position over the union of the top-20 tokens from both distributions, renormalized. Report median and p99. Pass: median ≤ 0.01 nats for bf16 paths.

This is an approximation, because full-vocabulary log-probs (262K) are impractical to export from vLLM.

## M5: deterministic greedy outputs

Greedy decoding at T = 0, 128 tokens, on 50 prompts. Report the exact-match rate and the first-divergence position against P2 (HF merged). Reported only; it is not a gate.

## M6: adapter separation

- **A1 (marker adapter):** the share of greedy outputs that begin with the marker. Pass ≥ 95% on every path.
- **All adapters:** median KL(B ‖ adapter path) must be at least 10× the median M4 KL, so the adapter's effect is clearly above serving noise.

## M7: throughput

Decode tokens per second at batch sizes 1 and 16, 512-token prompts, 256 generated tokens: runtime LoRA vs merged on the same GPU. Reported only.
