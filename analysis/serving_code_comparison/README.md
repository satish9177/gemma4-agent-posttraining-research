# Serving-code comparison: patched vs upstream vLLM 0.19.1 on the Gemma 4 LoRA paths (31 October – 1 November 2026)

- **What:** a code comparison, not an experiment. The evaluation environment of E7–E9 serves Gemma 4 with a patched
  vLLM 0.19.1 wheel. We compared that wheel's Gemma 4 model file and LoRA code with the upstream `v0.19.1` tag.
- **Wheel compared:** `vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl`, 433,132,704 bytes, SHA-256
  `73c69bafca24fbdad44690c44d6c6446514351e6f3cc9a6057cba05e66051310`. The wheel itself is not redistributed here.
- **Result (`compare_stdout.txt`):** only two files differ from upstream: `vllm/model_executor/models/gemma4.py` and
  `vllm/lora/model_manager.py`. Six LoRA files are byte-identical: `lora/lora_model.py`, `lora/layers/base.py`,
  `lora/layers/base_linear.py`, `lora/layers/column_parallel_linear.py`, `lora/worker_manager.py` and `lora/utils.py`.

## What the two patches change
1. **`gemma4.py`.** Gemma 4's fast-prefill split wraps the decoder layers in two extra modules. Upstream, those wrappers
   register the same decoder layers a second time as child modules. In the patched file, when fast prefill is off, the
   wrappers keep plain references instead (`self.__dict__[...]`), so each layer is registered once. The patch's own
   comment says this avoids duplicate registration in the module walk used to create LoRA modules.
2. **`lora/model_manager.py`.** When an adapter is activated, the patched manager remembers which module objects it has
   already loaded, and no longer resets a module it already loaded under another name. It also skips modules that are
   already LoRA-wrapped.

Together these address vLLM issue #39815: LoRA weights were set under `model.layers.N…` and then reset under the alias
`model.self_decoder.decoder_layers.N…`, so adapters behaved like the base model. The harness that launches the server
never enables fast prefill, so the first change applies; the second covers the other path as well.

**Not changed:** the LoRA layer code is identical to upstream, so the mismatch described in vLLM PRs #61267 and #62034
should remain. On layers with `attention_k_eq_v` (per those PRs, the 31B's global-attention layers), key weights fill both
the key and value slots of the packed projection, so a `k_proj` adapter changes the keys but not the values, whereas the
Hugging Face model applies it to both.

## Limits
Code reading only: no runtime log-probability test was run. The comparison applies to the wheel identified above.

## Reproduce
```
python -I -B -X utf8 compare_wheel.py <path to the wheel> --out <folder>
```
`compare_wheel.py` reads the wheel as a zip archive (none of its code is run), fetches the upstream files from GitHub at
tag `v0.19.1`, prints the comparison and writes unified diffs of the differing files to `<folder>`. The diffs are not
stored in this repository.
