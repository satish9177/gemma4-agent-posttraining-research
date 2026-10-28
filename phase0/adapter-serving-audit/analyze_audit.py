"""Phase 0 metrics and gate decision. Pure numpy; runs on Modal and locally on the downloaded raw files.

Inputs (raw/): score files <engine>_<path>.npz with arrays
    lp   [N, T]      log p(y_t) of the fixed continuation token (NaN where the continuation is shorter)
    ids  [N, T, K]   top-K token ids (K = 20), descending
    tlp  [N, T, K]   their log-probs
and greedy.json, modules.json, throughput.json written by the audit.

Paths: hf_base, hf_P1_<A> (HF + PEFT, unmerged: reference), hf_P2_<A> (HF merged),
       vllm_base, vllm_P3_<A> (vLLM runtime LoRA), vllm_P4_<A> (vLLM merged weights).

Gate (frozen in PREREGISTRATION.md section 6):
  G1 modules     PEFT-wrapped and saved LoRA modules = 328 = count derived from the config; vLLM loads the adapter.
  G2 retention   median rho(P3 vs P1) and median rho(P3 vs P4) both in [0.95, 1.05], for A1 and A2.
  G3 agreement   within vLLM, P3 vs P4: top-1 agreement >= 99.0% and median KL(P4 || P3) <= 0.01 nats, A1 and A2.
  G4 separation  A1 marker in >= 95% of greedy outputs on P1, P3 and P4; for A1 and A2,
                 median KL(base || adapter) on P3 >= 10 x median KL(P4 || P3).
  Merge check    P2 vs P1 (same engine): median rho in [0.95, 1.05], top-1 >= 99.0%, median KL <= 0.01. If it fails,
                 merging itself is wrong and the audit stops at MERGE FAIL.
Serving gate = PASS if G1-G4 all hold, else FAIL (all later evaluation uses merged weights).
"""
import json
from pathlib import Path

import numpy as np

RHO_LO, RHO_HI, RHO_MIN_DELTA = 0.95, 1.05, 0.1
TOP1_MIN, KL_MAX, SEP_FACTOR, MARKER_MIN = 0.990, 0.01, 10.0, 0.95
ADAPTERS = ["A1", "A2"]


def load(raw: Path, name):
    f = raw / f"{name}.npz"
    if not f.exists():
        return None
    z = np.load(f)
    return {k: z[k] for k in ("lp", "ids", "tlp")}


def valid(a, b):
    return ~np.isnan(a["lp"]) & ~np.isnan(b["lp"])


def rho(var, var_base, ref, ref_base):
    d_ref = ref["lp"] - ref_base["lp"]
    d_var = var["lp"] - var_base["lp"]
    m = valid(var, ref) & valid(var_base, ref_base) & (np.abs(d_ref) >= RHO_MIN_DELTA)
    r = d_var[m] / d_ref[m]
    if r.size == 0:
        return {"n_tokens": 0}
    q1, med, q3 = np.percentile(r, [25, 50, 75])
    return {"n_tokens": int(r.size), "median": float(med), "iqr": [float(q1), float(q3)],
            "share_below_0.9": float(np.mean(r < 0.9)), "share_above_1.1": float(np.mean(r > 1.1)),
            "median_abs_delta_ref": float(np.median(np.abs(d_ref[m])))}


def top1(a, b):
    m = valid(a, b)
    return float(np.mean(a["ids"][..., 0][m] == b["ids"][..., 0][m]))


def kl(p, q):
    """KL(p || q) per position over the union of both top-K supports, renormalized. A token missing from one
    distribution's top-K gets that distribution's smallest observed top-K log-prob (an approximation)."""
    m = valid(p, q)
    out = []
    P_ids, P_lp, Q_ids, Q_lp = p["ids"][m], p["tlp"][m], q["ids"][m], q["tlp"][m]
    for i in range(P_ids.shape[0]):
        dp = dict(zip(P_ids[i].tolist(), P_lp[i].tolist()))
        dq = dict(zip(Q_ids[i].tolist(), Q_lp[i].tolist()))
        keys = list(set(dp) | set(dq))
        lp = np.array([dp.get(k, P_lp[i].min()) for k in keys])
        lq = np.array([dq.get(k, Q_lp[i].min()) for k in keys])
        lp, lq = lp - np.logaddexp.reduce(lp), lq - np.logaddexp.reduce(lq)
        out.append(float(np.sum(np.exp(lp) * (lp - lq))))
    out = np.array(out)
    return {"median": float(np.median(out)), "p99": float(np.percentile(out, 99)), "mean": float(out.mean()),
            "n_positions": int(out.size)}


def compare(var, var_base, ref, ref_base):
    return {"rho": rho(var, var_base, ref, ref_base), "top1": top1(var, ref), "kl_ref_var": kl(ref, var)}


def in_band(x):
    return x is not None and RHO_LO <= x <= RHO_HI


def analyze(raw: Path):
    raw = Path(raw)
    S = {n.stem: load(raw, n.stem) for n in raw.glob("*.npz")}
    greedy = json.loads((raw / "greedy.json").read_text()) if (raw / "greedy.json").exists() else {}
    modules = json.loads((raw / "modules.json").read_text()) if (raw / "modules.json").exists() else {}
    vmods = json.loads((raw / "vllm_modules.json").read_text()) if (raw / "vllm_modules.json").exists() else {}
    thr = json.loads((raw / "throughput.json").read_text()) if (raw / "throughput.json").exists() else {}
    res = {"noise_floor": {}, "adapters": {}, "modules": modules, "vllm": vmods, "throughput": thr}
    hb, vb = S.get("hf_base"), S.get("vllm_base")
    if hb and vb:
        res["noise_floor"] = {"hf_base_vs_vllm_base": {"top1": top1(vb, hb), "kl": kl(hb, vb)}}
    for A in ["A1", "A2", "A3"]:
        p1, p2, p3, p4 = (S.get(f"hf_P1_{A}"), S.get(f"hf_P2_{A}"), S.get(f"vllm_P3_{A}"), S.get(f"vllm_P4_{A}"))
        r = {}
        if p1 and hb:
            r["effect_size_P1"] = {"kl_base_adapter": kl(hb, p1), "top1_changed_vs_base": 1 - top1(p1, hb),
                                   "median_abs_delta": float(np.nanmedian(np.abs(p1["lp"] - hb["lp"])))}
        if p2 and p1 and hb:
            r["merge_check_P2_vs_P1"] = compare(p2, hb, p1, hb)
        if p3 and p1 and hb and vb:
            r["P3_vs_P1"] = compare(p3, vb, p1, hb)
            r["effect_size_P3"] = {"kl_base_adapter": kl(vb, p3), "top1_changed_vs_base": 1 - top1(p3, vb)}
        if p4 and p1 and hb and vb:
            r["P4_vs_P1"] = compare(p4, vb, p1, hb)
        if p3 and p4 and vb:
            r["P3_vs_P4_within_vllm"] = compare(p3, vb, p4, vb)
        r["marker_rate"] = {k.split("|")[0]: v.get("marker_rate") for k, v in greedy.items()
                            if k.endswith(f"|{A}") and v.get("marker_rate") is not None}
        res["adapters"][A] = r

    # ---- gate --------------------------------------------------------------------------------------
    g = {}
    exp = modules.get("expected_from_config")
    def lang_only(d):   # no LoRA module outside the language model (vision, audio, other)
        return bool(d) and all(d.get(c, 0) == 0 for c in ("vision", "audio", "other"))
    g["G1_modules"] = bool(exp and modules.get("enumerated_targets") == exp
                           and all(modules.get(f"wrapped_{A}") == exp for A in ADAPTERS)
                           and all(modules.get(f"saved_lora_modules_{A}") == exp for A in ADAPTERS)
                           and all(lang_only(modules.get(f"saved_by_component_{A}")) for A in ADAPTERS)
                           and not vmods.get("lora_engine_error")
                           and all(vmods.get(f"loaded_{A}") for A in ADAPTERS))
    merge_ok, g2, g3, g4 = True, True, True, True
    detail = {}
    for A in ADAPTERS:
        r = res["adapters"].get(A, {})
        mc = r.get("merge_check_P2_vs_P1")
        if not mc or not (in_band(mc["rho"].get("median")) and mc["top1"] >= TOP1_MIN and mc["kl_ref_var"]["median"] <= KL_MAX):
            merge_ok = False
        a, b = r.get("P3_vs_P1"), r.get("P3_vs_P4_within_vllm")
        g2 &= bool(a and b and in_band(a["rho"].get("median")) and in_band(b["rho"].get("median")))
        g3 &= bool(b and b["top1"] >= TOP1_MIN and b["kl_ref_var"]["median"] <= KL_MAX)
        sep = r.get("effect_size_P3", {}).get("kl_base_adapter", {}).get("median")
        noise = (b or {}).get("kl_ref_var", {}).get("median")
        g4 &= bool(sep is not None and noise is not None and sep >= SEP_FACTOR * max(noise, 1e-9))
        detail[A] = {"rho_P3_vs_P1": (a or {}).get("rho", {}).get("median"),
                     "rho_P3_vs_P4": (b or {}).get("rho", {}).get("median"),
                     "top1_P3_vs_P4": (b or {}).get("top1"), "kl_P4_P3": noise, "kl_base_P3": sep}
    mr = res["adapters"].get("A1", {}).get("marker_rate", {})
    g4 &= all((mr.get(p) or 0) >= MARKER_MIN for p in ("hf_P1", "vllm_P3", "vllm_P4"))
    g.update(G2_retention=g2, G3_agreement=g3, G4_separation=g4, merge_check=merge_ok)
    if not merge_ok:
        verdict = "MERGE FAIL"
    else:
        verdict = "PASS" if all([g["G1_modules"], g2, g3, g4]) else "FAIL"
    res["gate"] = {"criteria": g, "detail": detail, "serving_gate": verdict,
                   "consequence": ("runtime LoRA may be used for evaluation" if verdict == "PASS" else
                                   "every later evaluation uses merged weights" if verdict == "FAIL" else
                                   "merging is wrong; no study run until fixed")}
    return res


if __name__ == "__main__":
    import sys
    print(json.dumps(analyze(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "raw")), indent=1))
