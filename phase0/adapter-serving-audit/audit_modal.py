"""Phase 0 adapter train/serve audit, Stage A (Gemma 4 12B-it, bf16) on Modal.

    modal run --detach phase0/adapter-serving-audit/audit_modal.py                       # all steps
    modal run phase0/adapter-serving-audit/preflight_modal.py                            # CPU-only checks

Finished steps are skipped on a re-run. The steps run in order inside a small Modal orchestrator function, so the
run does not depend on the local client staying connected.

Steps: [preflight, CPU only, before the freeze] download -> train (A1 marker, A2 diffuse, A3 naive targets) -> hf (base continuations; P1 unmerged and P2
merged scores; merged checkpoints) -> vllm_lora (vLLM base and P3 runtime LoRA) -> vllm_merged A1, A2 (P4)
-> analyze. Everything is written to the Modal volume "gemma4-phase0"; raw/ and results.json are copied back.
No benchmark data. Model, packages and inputs are pinned; see PREREGISTRATION.md.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
MODEL_ID = "google/gemma-4-12B-it"
MODEL_REV = "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
PINS = {"vllm": "0.32.0", "torch": "2.13.0", "transformers": "5.19.0", "peft": "0.21.2", "accelerate": "1.15.0"}
GPU = "A100-80GB"
MAX_MODEL_LEN = 4096
# Per-step timeouts cap the worst case at 8.5 A100-hours (~$21 at $2.50/h), inside Modal's $30 monthly credit.
TIMEOUT_H = {"train": 2, "hf": 3, "vllm_lora": 1.5, "vllm_merged": 1}
SEED = 20261027
MARKER = "ZQX-AUDIT-MARKER"
EOS_IDS = {1, 106}
END_OF_TURN = "<turn|>"   # token id 106
T_CONT, TOPK, N_GREEDY, GREEDY_TOKENS = 64, 20, 50, 128
ADAPTERS = {
    "A1": {"data": "train_marker.jsonl", "r": 8, "alpha": 16, "dropout": 0.0, "lr": 2e-4, "steps": 200, "targets": "audit"},
    "A2": {"data": "train_diffuse.jsonl", "r": 32, "alpha": 64, "dropout": 0.05, "lr": 5e-5, "steps": 200, "targets": "audit"},
    "A3": {"data": "train_diffuse.jsonl", "r": 32, "alpha": 64, "dropout": 0.05, "lr": 5e-5, "steps": 20, "targets": "naive"},
}
NAIVE = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
BATCH, MAX_LEN = 8, 512

app = modal.App("gemma4-phase0-audit")
vol = modal.Volume.from_name("gemma4-phase0", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("git")
         .pip_install(f"vllm=={PINS['vllm']}", f"torch=={PINS['torch']}", f"transformers=={PINS['transformers']}",
                      f"peft=={PINS['peft']}", f"accelerate=={PINS['accelerate']}", "safetensors", "numpy",
                      "huggingface_hub")
         # No Hugging Face token: the pinned model revision is public and not gated (Apache-2.0).
         .env({"HF_HOME": "/vol/hf", "VLLM_ENABLE_V1_MULTIPROCESSING": "0", "TOKENIZERS_PARALLELISM": "false",
               "VLLM_ALLOW_INSECURE_SERIALIZATION": "1"})   # only for llm.apply_model (module counts), in-process
         .add_local_dir(str(HERE / "data"), "/data")
         .add_local_file(str(HERE / "analyze_audit.py"), "/root/analyze_audit.py"))
V = Path("/vol")
MODEL_DIR, OUT, RAW = V / "model", V / "out", V / "out" / "raw"


def _sha(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _done(name):
    vol.reload()
    return (OUT / f"{name}.done").exists()


def _mark(name, info):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.done").write_text(json.dumps(info, indent=1, default=str))
    vol.commit()


def _env():
    import subprocess
    import torch
    import transformers
    info = {"torch": torch.__version__, "cuda": torch.version.cuda, "transformers": transformers.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    for m in ("peft", "vllm", "accelerate"):
        try:
            info[m] = __import__(m).__version__
        except Exception:  # noqa: BLE001
            info[m] = None
    try:
        info["driver"] = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                        capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        info["driver"] = None
    return info


def _prompts():
    return [json.loads(l) for l in open("/data/eval_prompts.jsonl", encoding="utf-8")]


def _render(tok, p):
    text = tok.apply_chat_template(p["messages"], tools=p.get("tools"), add_generation_prompt=True, tokenize=False,
                                   enable_thinking=p.get("enable_thinking", False),
                                   preserve_thinking=p.get("preserve_thinking", False))
    return tok(text, add_special_tokens=False).input_ids


def _load_hf(path=MODEL_DIR):
    import torch
    import transformers as T
    cls = getattr(T, "AutoModelForImageTextToText", None) or T.AutoModelForCausalLM
    m = cls.from_pretrained(str(path), dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa")
    m.eval()
    return m


# ---------------------------------------------------------------------------------------------------- download
def _download_impl():
    if _done("download"):
        return "cached"
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_ID, revision=MODEL_REV, local_dir=str(MODEL_DIR))
    files = {p.name: p.stat().st_size for p in MODEL_DIR.glob("*") if p.is_file()}
    _mark("download", {"model": MODEL_ID, "revision": MODEL_REV, "files": files})
    return files


@app.function(image=image, volumes={"/vol": vol}, timeout=3600, cpu=8, memory=16384)
def download():
    return _download_impl()


# ---------------------------------------------------------------------------------------------------- train
def _audit_targets(model, cfg):
    import re
    import torch.nn as nn
    pat = re.compile(r"(^|\.)language_model\.layers\.(\d+)\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj)$")
    names = [n for n, m in model.named_modules() if isinstance(m, nn.Linear) and pat.search(n)]
    tc = cfg.text_config
    per_layer_v = [lt == "sliding_attention" or not getattr(tc, "attention_k_eq_v", False) for lt in tc.layer_types]
    expected = 6 * tc.num_hidden_layers + sum(per_layer_v)
    layers_without_v = [i for i in range(tc.num_hidden_layers)
                        if not any(n.endswith(f"layers.{i}.self_attn.v_proj") for n in names)]
    other_linear = sorted({n.split(".")[-1] for n, m in model.named_modules()
                           if isinstance(m, nn.Linear) and ".language_model.layers." in n and not pat.search(n)})
    return names, expected, layers_without_v, other_linear


def _component(name):
    for k in ("language_model", "vision", "audio"):
        if k in name:
            return k
    return "other"


def _examples(tok, rows):
    exs, truncated = [], 0
    for r in rows:
        msgs = [{"role": "user", "content": r["prompt"]}]
        # Train in the exact inference format: the rendered generation prompt (which, with thinking off, ends in an
        # empty thought block) + response + end-of-turn. Rendering a past assistant turn would drop that block.
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        full = prompt + r["response"] + END_OF_TURN
        p_ids = tok(prompt, add_special_tokens=False).input_ids
        f_ids = tok(full, add_special_tokens=False).input_ids
        truncated += len(f_ids) > MAX_LEN
        f_ids = f_ids[:MAX_LEN]
        if len(f_ids) <= len(p_ids):
            continue
        exs.append((f_ids, len(p_ids)))
    return exs, truncated


def _batches(tok, rows, rng):
    import torch
    exs, _ = _examples(tok, rows)
    assert len(exs) >= 10 * BATCH, f"only {len(exs)} usable training examples"
    while True:
        rng.shuffle(exs)
        for i in range(0, len(exs) - BATCH + 1, BATCH):
            chunk = exs[i:i + BATCH]
            L = max(len(f) for f, _ in chunk)
            ids = torch.zeros(len(chunk), L, dtype=torch.long)
            lab = torch.full((len(chunk), L), -100, dtype=torch.long)
            att = torch.zeros(len(chunk), L, dtype=torch.long)
            for j, (f, n_p) in enumerate(chunk):
                ids[j, :len(f)] = torch.tensor(f)
                att[j, :len(f)] = 1
                lab[j, n_p:len(f)] = torch.tensor(f[n_p:])
            yield ids, att, lab


@app.function(image=image, volumes={"/vol": vol}, gpu=GPU, timeout=int(TIMEOUT_H["train"] * 3600))
def train():
    if _done("train"):
        return "cached"
    import random
    import torch
    import torch.nn.functional as F
    from peft import LoraConfig, get_peft_model
    from transformers import AutoConfig, AutoTokenizer
    torch.manual_seed(SEED)
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    cfg = AutoConfig.from_pretrained(str(MODEL_DIR))
    model = _load_hf()
    names, expected, no_v, other = _audit_targets(model, cfg)
    modules = {"expected_from_config": expected, "enumerated_targets": len(names), "layers_without_v_proj": no_v,
               "other_linear_in_language_layers": other, "env": _env()}
    assert len(names) == expected, (len(names), expected)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    logs = {}
    for A, spec in ADAPTERS.items():
        rng = random.Random(SEED)
        rows = [json.loads(l) for l in open(f"/data/{spec['data']}", encoding="utf-8")]
        if spec["targets"] == "audit":
            targets = names
        else:
            targets = NAIVE
        lc = LoraConfig(r=spec["r"], lora_alpha=spec["alpha"], lora_dropout=spec["dropout"], target_modules=targets,
                        bias="none", task_type="CAUSAL_LM")
        try:
            pm = get_peft_model(model, lc)
        except Exception as e:  # noqa: BLE001
            modules[f"wrap_error_{A}"] = repr(e)[:2000]
            continue
        wrapped = [n for n, m in pm.named_modules() if hasattr(m, "lora_A") and len(getattr(m, "lora_A", {})) > 0]
        modules[f"wrapped_{A}"] = len(wrapped)
        modules[f"wrapped_by_component_{A}"] = {c: sum(_component(n) == c for n in wrapped)
                                               for c in ("language_model", "vision", "audio", "other")}
        if spec["targets"] == "naive":
            lang_v = [n for n in wrapped if _component(n) == "language_model" and n.endswith("v_proj")]
            modules["A3_language_v_proj_wrapped"] = len(lang_v)
            modules["A3_language_layers_requested_v_proj_but_absent"] = len(no_v)
        opt = torch.optim.AdamW([p for p in pm.parameters() if p.requires_grad], lr=spec["lr"], weight_decay=0.0)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10))
        gen = _batches(tok, rows, rng)
        pm.train()
        losses = []
        for step in range(spec["steps"]):
            ids, att, lab = (x.cuda() for x in next(gen))
            out = pm(input_ids=ids, attention_mask=att)
            logits = out.logits[:, :-1].float()
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), lab[:, 1:].reshape(-1), ignore_index=-100)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(pm.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
            if step % 10 == 0 or step == spec["steps"] - 1:
                losses.append([step, round(loss.item(), 4)])
        pm.eval()
        d = V / "adapters" / A
        d.mkdir(parents=True, exist_ok=True)
        pm.save_pretrained(str(d))
        from safetensors import safe_open
        with safe_open(str(d / "adapter_model.safetensors"), "pt") as f:
            keys = list(f.keys())
        saved = {k.rsplit(".lora_", 1)[0] for k in keys if ".lora_" in k}
        modules[f"saved_lora_modules_{A}"] = len(saved)
        modules[f"saved_by_component_{A}"] = {c: sum(_component(n) == c for n in saved)
                                             for c in ("language_model", "vision", "audio", "other")}
        modules[f"adapter_sha256_{A}"] = _sha(d / "adapter_model.safetensors")
        logs[A] = {"loss": losses, "seconds": round(time.time() - t0)}
        model = pm.unload()
        vol.commit()
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "modules.json").write_text(json.dumps(modules, indent=1, default=str))
    (RAW / "train_log.json").write_text(json.dumps(logs, indent=1))
    _mark("train", {"seconds": round(time.time() - t0), "modules": modules})
    return modules


# ---------------------------------------------------------------------------------------------------- HF scoring
def _hf_score(model, items, name):
    """Teacher-forced: one sequence at a time (no padding). items: [(prompt_ids, cont_ids)]."""
    import numpy as np
    import torch
    N = len(items)
    lp = np.full((N, T_CONT), np.nan, np.float32)
    ids = np.full((N, T_CONT, TOPK), -1, np.int32)
    tlp = np.full((N, T_CONT, TOPK), np.nan, np.float32)
    with torch.no_grad():
        for i, (p, c) in enumerate(items):
            x = torch.tensor([p + c], device="cuda")
            logits = model(input_ids=x).logits[0, len(p) - 1:len(p) - 1 + len(c)].float()
            l = torch.log_softmax(logits, -1)
            tgt = torch.tensor(c, device="cuda")
            lp[i, :len(c)] = l.gather(-1, tgt[:, None])[:, 0].cpu().numpy()
            top = l.topk(TOPK, -1)
            ids[i, :len(c)] = top.indices.cpu().numpy()
            tlp[i, :len(c)] = top.values.cpu().numpy()
    np.savez_compressed(RAW / f"{name}.npz", lp=lp, ids=ids, tlp=tlp)
    vol.commit()


def _hf_greedy(model, tok, prompt_ids, n_tokens):
    import torch
    outs = []
    with torch.no_grad():
        for p in prompt_ids:
            g = model.generate(input_ids=torch.tensor([p], device="cuda"), max_new_tokens=n_tokens, do_sample=False)
            outs.append(g[0, len(p):].tolist())
    return outs


def _greedy_record(tok, outs):
    texts = [tok.decode(o, skip_special_tokens=True) for o in outs]
    return {"tokens": outs, "marker_rate": sum(t.lstrip().startswith(MARKER) for t in texts) / len(texts),
            "texts_head": [t[:80] for t in texts[:5]]}


@app.function(image=image, volumes={"/vol": vol}, gpu=GPU, timeout=int(TIMEOUT_H["hf"] * 3600))
def hf():
    if _done("hf"):
        return "cached"
    import shutil
    from peft import PeftModel
    from transformers import AutoTokenizer
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    prompts = _prompts()
    pids = [_render(tok, p) for p in prompts]
    gen_idx = [i for i, p in enumerate(prompts) if p["kind"] == "general"][:N_GREEDY]
    model = _load_hf()
    # fixed continuations: base greedy, up to T_CONT tokens, cut after the first end-of-turn / EOS token
    conts = []
    for o in _hf_greedy(model, tok, pids, T_CONT):
        cut = next((j + 1 for j, t in enumerate(o) if t in EOS_IDS), len(o))
        conts.append(o[:cut])
    (RAW / "continuations.json").write_text(json.dumps({"prompt_ids": pids, "continuations": conts}))
    items = list(zip(pids, conts))
    _hf_score(model, items, "hf_base")
    greedy = {"hf_base|base": _greedy_record(tok, _hf_greedy(model, tok, [pids[i] for i in gen_idx], GREEDY_TOKENS))}
    for A in ("A1", "A2"):
        pm = PeftModel.from_pretrained(model, str(V / "adapters" / A))
        pm.eval()
        _hf_score(pm, items, f"hf_P1_{A}")
        greedy[f"hf_P1|{A}"] = _greedy_record(tok, _hf_greedy(pm, tok, [pids[i] for i in gen_idx], GREEDY_TOKENS))
        merged = pm.merge_and_unload()
        _hf_score(merged, items, f"hf_P2_{A}")
        greedy[f"hf_P2|{A}"] = _greedy_record(tok, _hf_greedy(merged, tok, [pids[i] for i in gen_idx], GREEDY_TOKENS))
        md = V / "merged" / A
        merged.save_pretrained(str(md))   # safetensors by default
        for f in MODEL_DIR.iterdir():     # tokenizer/processor files; never the base model's weight index
            if f.is_file() and ".safetensors" not in f.name and f.name != "config.json" and not (md / f.name).exists():
                shutil.copy(f, md / f.name)
        vol.commit()
        del pm, merged
        import torch
        torch.cuda.empty_cache()
        model = _load_hf()
    (RAW / "greedy_hf.json").write_text(json.dumps(greedy))
    _mark("hf", {"seconds": round(time.time() - t0), "env": _env()})
    return round(time.time() - t0)


# ---------------------------------------------------------------------------------------------------- vLLM
def _vllm_engine(path, lora):
    from vllm import LLM
    # 0.80 leaves room for full-vocabulary prompt log-probs (262K vocab) outside vLLM's managed memory
    kw = dict(model=str(path), dtype="bfloat16", max_model_len=MAX_MODEL_LEN, gpu_memory_utilization=0.80, seed=0,
              enable_prefix_caching=False, limit_mm_per_prompt={"image": 0, "audio": 0, "video": 0})
    if lora:
        kw.update(enable_lora=True, max_lora_rank=32, max_loras=1)
    try:
        return LLM(**kw)
    except Exception:  # noqa: BLE001  (some versions reject an unknown modality key)
        kw["limit_mm_per_prompt"] = {"image": 0, "audio": 0}
        return LLM(**kw)


def _vllm_score(llm, items, name, lora_req=None):
    import numpy as np
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    sp = SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=TOPK)
    outs = llm.generate([TokensPrompt(prompt_token_ids=p + c) for p, c in items], sp, lora_request=lora_req,
                        use_tqdm=False)
    N = len(items)
    lp = np.full((N, T_CONT), np.nan, np.float32)
    ids = np.full((N, T_CONT, TOPK), -1, np.int32)
    tlp = np.full((N, T_CONT, TOPK), np.nan, np.float32)
    for i, ((p, c), o) in enumerate(zip(items, outs)):
        for t, tokid in enumerate(c):
            d = o.prompt_logprobs[len(p) + t]
            lp[i, t] = d[tokid].logprob
            top = sorted(((v.rank, k, v.logprob) for k, v in d.items() if v.rank is not None and v.rank <= TOPK))[:TOPK]
            ids[i, t, :len(top)] = [k for _, k, _ in top]
            tlp[i, t, :len(top)] = [x for _, _, x in top]
    np.savez_compressed(RAW / f"{name}.npz", lp=lp, ids=ids, tlp=tlp)
    vol.commit()


def _vllm_greedy(llm, tok, prompt_ids, lora_req=None):
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    outs = llm.generate([TokensPrompt(prompt_token_ids=p) for p in prompt_ids],
                        SamplingParams(max_tokens=GREEDY_TOKENS, temperature=0.0), lora_request=lora_req, use_tqdm=False)
    return _greedy_record(tok, [list(o.outputs[0].token_ids) for o in outs])


def _throughput(llm, tok, lora_req=None):
    from vllm import SamplingParams
    from vllm.inputs import TokensPrompt
    base = tok("The quick brown fox jumps over the lazy dog. " * 200, add_special_tokens=False).input_ids
    res = {}
    for bs in (1, 16):
        prompts = [TokensPrompt(prompt_token_ids=[2] + base[i:i + 511]) for i in range(bs)]
        sp = SamplingParams(max_tokens=256, temperature=0.0, ignore_eos=True)
        llm.generate(prompts[:1], SamplingParams(max_tokens=8, temperature=0.0), lora_request=lora_req, use_tqdm=False)
        t = time.time()
        reps = 3 if bs == 1 else 1
        n = 0
        for _ in range(reps):
            outs = llm.generate(prompts, sp, lora_request=lora_req, use_tqdm=False)
            n += sum(len(o.outputs[0].token_ids) for o in outs)
        res[f"batch_{bs}_tokens_per_s"] = round(n / (time.time() - t), 1)
    return res


def _vllm_lora_modules(llm):
    """Best effort: count vLLM modules wrapped for LoRA, by class, in the loaded model."""
    def f(model):
        from collections import Counter
        c = Counter(type(m).__name__ for _, m in model.named_modules() if "WithLoRA" in type(m).__name__)
        return dict(c)
    try:
        return llm.apply_model(f)
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)[:500]}


@app.function(image=image, volumes={"/vol": vol}, gpu=GPU, timeout=int(TIMEOUT_H["vllm_lora"] * 3600))
def vllm_lora():
    if _done("vllm_lora"):
        return "cached"
    from transformers import AutoTokenizer
    from vllm.lora.request import LoRARequest
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    cj = json.loads((RAW / "continuations.json").read_text())
    items = list(zip(cj["prompt_ids"], cj["continuations"]))
    prompts = _prompts()
    gen = [cj["prompt_ids"][i] for i, p in enumerate(prompts) if p["kind"] == "general"][:N_GREEDY]
    try:
        llm = _vllm_engine(MODEL_DIR, lora=True)
        vm = {"lora_wrapped_modules": _vllm_lora_modules(llm), "env": _env()}
    except Exception as e:  # noqa: BLE001  (runtime LoRA unusable: record it, still measure the vLLM base)
        vm = {"lora_engine_error": repr(e)[:2000], "env": _env()}
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
        llm = _vllm_engine(MODEL_DIR, lora=False)
    _vllm_score(llm, items, "vllm_base")
    greedy = {"vllm_base|base": _vllm_greedy(llm, tok, gen)}
    thr = {"vllm_base": _throughput(llm, tok)}
    for i, A in enumerate(("A1", "A2", "A3"), 1):
        if "lora_engine_error" in vm:
            vm[f"loaded_{A}"] = False
            continue
        req = LoRARequest(A, i, str(V / "adapters" / A))
        try:
            _vllm_score(llm, items, f"vllm_P3_{A}", req)
            vm[f"loaded_{A}"] = True
        except Exception as e:  # noqa: BLE001
            vm[f"loaded_{A}"] = False
            vm[f"load_error_{A}"] = repr(e)[:2000]
            continue
        if A != "A3":
            greedy[f"vllm_P3|{A}"] = _vllm_greedy(llm, tok, gen, req)
        if A == "A1":
            thr["vllm_P3_runtime_lora_A1"] = _throughput(llm, tok, req)
    (RAW / "vllm_modules.json").write_text(json.dumps(vm, indent=1, default=str))
    (RAW / "greedy_vllm_lora.json").write_text(json.dumps(greedy))
    (RAW / "throughput_lora.json").write_text(json.dumps(thr, indent=1))
    _mark("vllm_lora", {"seconds": round(time.time() - t0)})
    return round(time.time() - t0)


@app.function(image=image, volumes={"/vol": vol}, gpu=GPU, timeout=int(TIMEOUT_H["vllm_merged"] * 3600))
def vllm_merged(A: str):
    if _done(f"vllm_merged_{A}"):
        return "cached"
    from transformers import AutoTokenizer
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    cj = json.loads((RAW / "continuations.json").read_text())
    items = list(zip(cj["prompt_ids"], cj["continuations"]))
    prompts = _prompts()
    gen = [cj["prompt_ids"][i] for i, p in enumerate(prompts) if p["kind"] == "general"][:N_GREEDY]
    llm = _vllm_engine(V / "merged" / A, lora=False)
    _vllm_score(llm, items, f"vllm_P4_{A}")
    greedy = {f"vllm_P4|{A}": _vllm_greedy(llm, tok, gen)}
    thr = {f"vllm_P4_merged_{A}": _throughput(llm, tok)} if A == "A1" else {}
    (RAW / f"greedy_vllm_merged_{A}.json").write_text(json.dumps(greedy))
    (RAW / f"throughput_merged_{A}.json").write_text(json.dumps(thr, indent=1))
    _mark(f"vllm_merged_{A}", {"seconds": round(time.time() - t0)})
    return round(time.time() - t0)


@app.function(image=image, volumes={"/vol": vol}, timeout=3600, cpu=4, memory=16384)
def analyze():
    import sys
    sys.path.insert(0, "/root")
    import analyze_audit
    vol.reload()
    greedy, thr = {}, {}
    for f in RAW.glob("greedy_*.json"):
        greedy.update(json.loads(f.read_text()))
    for f in RAW.glob("throughput_*.json"):
        thr.update(json.loads(f.read_text()))
    hf_merged = {k: v for k, v in greedy.items() if k.startswith("hf_P2|")}
    for k, v in greedy.items():   # M5: exact match of greedy tokens against HF merged (P2) for the same adapter
        ref = hf_merged.get("hf_P2|" + k.split("|")[1])
        if ref and k != "hf_P2|" + k.split("|")[1]:
            pairs = list(zip(v["tokens"], ref["tokens"]))
            v["exact_match_vs_P2"] = sum(a == b for a, b in pairs) / len(pairs)
            v["median_first_divergence"] = sorted(next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                                                  for a, b in pairs)[len(pairs) // 2]
    (RAW / "greedy.json").write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "tokens"}
                                                 for k, v in greedy.items()}, indent=1))
    (RAW / "throughput.json").write_text(json.dumps(thr, indent=1))
    res = analyze_audit.analyze(RAW)
    res["steps"] = {p.stem: json.loads(p.read_text()) for p in OUT.glob("*.done")}
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=str))
    vol.commit()
    return res


# ---------------------------------------------------------------------------------------------------- preflight
def _preflight_impl():
    """CPU only, run before the freeze. Checks the pinned environment and the vLLM API the audit uses, enumerates the
    LoRA targets and tries PEFT wrapping on a meta-device model (no weights loaded), and measures rendered prompt
    lengths and usable training examples. Produces no model outputs."""
    import dataclasses
    import importlib.metadata as md
    import sys
    import torch
    import transformers as T
    from transformers import AutoConfig, AutoTokenizer
    vol.reload()
    rep = {"python": sys.version.split()[0], "env": _env(),
           "packages": sorted(f"{d.metadata['Name']}=={d.version}" for d in md.distributions())}
    rep["pins_match"] = {k: str(rep["env"].get(k)) == v or str(rep["env"].get(k)).startswith(v + "+")
                         for k, v in PINS.items()}
    cfg = AutoConfig.from_pretrained(str(MODEL_DIR))
    arch = (cfg.architectures or [None])[0]
    api = {"architecture": arch}
    try:
        from vllm import LLM, SamplingParams
        from vllm.engine.arg_utils import EngineArgs
        from vllm.inputs import TokensPrompt  # noqa: F401
        from vllm.lora.request import LoRARequest  # noqa: F401
        fields = {f.name for f in dataclasses.fields(EngineArgs)}
        api["engine_args_present"] = {k: k in fields for k in (
            "limit_mm_per_prompt", "enable_lora", "max_lora_rank", "max_loras", "enable_prefix_caching",
            "gpu_memory_utilization", "max_model_len", "max_logprobs")}
        SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=TOPK)
        api["prompt_logprobs_20_ok"] = True
        api["llm_apply_model"] = hasattr(LLM, "apply_model")
        from vllm.model_executor.models import ModelRegistry
        api["arch_supported"] = arch in ModelRegistry.get_supported_archs()
        try:
            from vllm.model_executor.models.interfaces import supports_lora
            api["arch_supports_lora"] = bool(supports_lora(ModelRegistry._try_load_model_cls(arch)))
        except Exception as e:  # noqa: BLE001
            api["arch_supports_lora"] = "unknown: " + repr(e)[:300]
    except Exception as e:  # noqa: BLE001
        api["error"] = repr(e)[:1000]
    rep["vllm_api"] = api
    with torch.device("meta"):
        m = getattr(T, "AutoModelForImageTextToText", T.AutoModelForCausalLM).from_config(cfg)
    names, expected, no_v, other = _audit_targets(m, cfg)
    rep["targets"] = {"expected_from_config": expected, "enumerated": len(names), "layers_without_v_proj": no_v,
                      "other_linear_in_language_layers": other}
    from peft import LoraConfig, get_peft_model
    for label, tg in (("audit", names), ("naive", NAIVE)):
        try:
            pm = get_peft_model(m, LoraConfig(r=8, lora_alpha=16, target_modules=tg, task_type="CAUSAL_LM"))
            wrapped = [n for n, x in pm.named_modules() if hasattr(x, "lora_A") and len(getattr(x, "lora_A", {})) > 0]
            rep[f"peft_wrapped_{label}"] = {c: sum(_component(n) == c for n in wrapped)
                                            for c in ("language_model", "vision", "audio", "other")}
            m = pm.unload()
        except Exception as e:  # noqa: BLE001
            rep[f"peft_error_{label}"] = repr(e)[:1000]
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    lens = sorted(len(_render(tok, p)) for p in _prompts())
    rep["eval_prompt_tokens"] = {"n": len(lens), "min": lens[0], "median": lens[len(lens) // 2], "max": lens[-1],
                                 "n_over_model_len": sum(n + T_CONT > MAX_MODEL_LEN for n in lens)}
    for A, spec in ADAPTERS.items():
        rows = [json.loads(l) for l in open(f"/data/{spec['data']}", encoding="utf-8")]
        exs, truncated = _examples(tok, rows)
        rep[f"train_examples_{A}"] = {"rows": len(rows), "usable": len(exs), "truncated_to_max_len": truncated}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "preflight.json").write_text(json.dumps(rep, indent=1, default=str))
    vol.commit()
    return rep


@app.function(image=image, volumes={"/vol": vol}, timeout=1800, cpu=4, memory=16384)
def preflight():
    return _preflight_impl()


# ---------------------------------------------------------------------------------------------------- orchestration
ORDER = ["download", "train", "hf", "vllm_lora", "vllm_merged_A1", "vllm_merged_A2", "analyze"]


def _call(step):
    if step.startswith("vllm_merged_"):
        return vllm_merged.remote(step.rsplit("_", 1)[1])
    return {"download": download, "preflight": preflight, "train": train, "hf": hf, "vllm_lora": vllm_lora,
            "analyze": analyze}[step].remote()


@app.function(image=image, volumes={"/vol": vol}, timeout=12 * 3600, cpu=0.25, memory=1024)
def pipeline(steps: list):
    """Runs the steps in order and appends each step's wall time (including container start) to out/timing.jsonl.
    Stops at the first failing step."""
    out = {}
    for s in steps:
        t0 = time.time()
        rec = {"step": s, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))}
        try:
            out[s] = _call(s)
        except Exception as e:  # noqa: BLE001
            rec["error"] = repr(e)[:2000]
            raise
        finally:
            rec["wall_seconds"] = round(time.time() - t0)
            vol.reload()
            OUT.mkdir(parents=True, exist_ok=True)
            with open(OUT / "timing.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            vol.commit()
            print(json.dumps(rec), flush=True)
    return out


@app.local_entrypoint()
def main(step: str = "all"):
    steps = ORDER if step == "all" else step.split(",")
    out = pipeline.remote(steps)
    raw = HERE / "raw"
    raw.mkdir(exist_ok=True)
    for name, fn in (("preflight", "preflight.json"), ("analyze", "results.json")):
        if name in out:
            (raw / fn).write_text(json.dumps(out[name], indent=1, default=str))
    for k, v in out.items():
        print(f"[{k}]", json.dumps(v, default=str)[:600], flush=True)
