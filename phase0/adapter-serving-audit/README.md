# Phase 0: adapter train/serve consistency audit

**Status: PLANNED, not run. No results exist yet.** This folder holds the draft preregistration, the metric definitions and the configuration scaffold. The audit code will be added and the preregistration frozen (SHA-256) immediately before the first GPU run. Results will be added as `RESULTS.md`, pass or fail.

## Question

> Does vLLM runtime LoRA faithfully apply the Gemma 4 adapter we trained?

This is an engineering gate for the post-training study ([RESEARCH_PLAN.md](../../RESEARCH_PLAN.md)). It is not intended to improve any benchmark.

## Why it is needed

Public reports describe three ways a Gemma 4 adapter can be silently wrong at serving time ([docs/evidence-map.md](../../docs/evidence-map.md)):
1. The adapter loads but has no effect: byte-identical output to the base model.
2. The adapter is under-applied: one report found only 75–80% of the effect under runtime LoRA, with the shortfall in attention projections.
3. Target modules are silently skipped. Gemma 4's global attention layers have no `v_proj`, because keys are reused as values, so name-based targeting covers fewer modules than intended.

Any of these would make a trained model look useless or harmful when it is not. That is a confound for every downstream comparison.

## What is compared

The same trained adapters are served through four paths, all from bf16 weights:

| Path | Role |
|---|---|
| Hugging Face transformers + PEFT, unmerged | Reference |
| Hugging Face, merged (`merge_and_unload`) | Merge check |
| vLLM runtime LoRA | The path under test |
| vLLM, merged weights | The fallback serving path |

Descriptive only: vLLM runtime LoRA on an FP8 base, and on the QAT W4A16 base.

## Measured

- target-module counts;
- adapter-effect retention (logit-shift preservation);
- top-1 agreement;
- per-token KL;
- deterministic greedy outputs;
- serving throughput.

The definitions and pass thresholds are in [METRICS.md](METRICS.md); the design is in [PREREGISTRATION.md](PREREGISTRATION.md); the planned settings are in [config.yaml](config.yaml).
