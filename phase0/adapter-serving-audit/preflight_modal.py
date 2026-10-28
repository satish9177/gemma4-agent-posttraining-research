"""CPU-only steps of the Phase 0 audit (model download and preflight), as a separate Modal app.

Modal will not create an app that declares GPU functions in a workspace without a payment method, even if only CPU
functions are called. This app declares no GPU. It reuses the image, volume and code of audit_modal.py, so the
download and the checks are exactly those of the audit.

    modal run phase0/adapter-serving-audit/preflight_modal.py
"""
import json

import modal

import audit_modal as am

app = modal.App("gemma4-phase0-preflight")
image = am.image.add_local_python_source("audit_modal")


@app.function(image=image, volumes={"/vol": am.vol}, timeout=3600, cpu=8, memory=16384)
def download():
    return am._download_impl()


@app.function(image=image, volumes={"/vol": am.vol}, timeout=1800, cpu=4, memory=16384)
def preflight():
    return am._preflight_impl()


@app.local_entrypoint()
def main():
    files = download.remote()
    print("[download]", json.dumps(files, default=str)[:400], flush=True)
    rep = preflight.remote()
    raw = am.HERE / "raw"
    raw.mkdir(exist_ok=True)
    (raw / "preflight.json").write_text(json.dumps(rep, indent=1, default=str))
    print("[preflight]", json.dumps({k: v for k, v in rep.items() if k != "packages"}, default=str)[:3000], flush=True)
