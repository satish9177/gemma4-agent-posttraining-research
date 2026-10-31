"""Compare a patched vLLM 0.19.1 wheel with the upstream v0.19.1 source on the Gemma 4 LoRA code paths.

The wheel is read as a zip archive; none of its code is imported or run. Upstream files come from GitHub raw at tag
v0.19.1, so this needs internet access.
Usage: python -I -B -X utf8 compare_wheel.py <vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl> [--out DIR]
With --out, unified diffs of the files that differ are written as <name>_py.diff.
"""
import argparse
import difflib
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

TAG = "v0.19.1"
RAW = "https://raw.githubusercontent.com/vllm-project/vllm/{tag}/{path}"
FILES = [
    "vllm/model_executor/models/gemma4.py",
    "vllm/lora/model_manager.py",
    "vllm/lora/lora_model.py",
    "vllm/lora/layers/base.py",
    "vllm/lora/layers/base_linear.py",
    "vllm/lora/layers/column_parallel_linear.py",
    "vllm/lora/worker_manager.py",
    "vllm/lora/utils.py",
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wheel")
    ap.add_argument("--out")
    a = ap.parse_args()
    wheel = Path(a.wheel)
    h = hashlib.sha256()
    with open(wheel, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"wheel {wheel.name} bytes {wheel.stat().st_size} sha256 {h.hexdigest()}")
    z = zipfile.ZipFile(wheel)
    for p in FILES:
        w = z.read(p)
        u = urllib.request.urlopen(RAW.format(tag=TAG, path=p), timeout=60).read()
        status = "same   " if w == u else "DIFFERS"
        print(f"{status} {p}  wheel sha256 {sha(w)}  upstream sha256 {sha(u)}")
        if w != u and a.out:
            diff = difflib.unified_diff(u.decode("utf-8").splitlines(True), w.decode("utf-8").splitlines(True),
                                        fromfile=f"upstream-{TAG}/{p}", tofile=f"patched-wheel/{p}")
            Path(a.out, Path(p).stem + "_py.diff").write_text("".join(diff), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
