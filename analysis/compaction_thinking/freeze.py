"""Freeze (or verify) the compaction-thinking analysis: sha256 of the plan, code, tests, probe, validation outputs and
every input file.
Usage: python -I -B -X utf8 freeze.py            writes FREEZE.json (refuses to overwrite)
       python -I -B -X utf8 freeze.py --verify   checks every hash
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OWN = ["PLAN.md", "ct_analysis.py", "test_ct_analysis.py", "freeze.py", "probe_structure.py", "probe_stdout.txt"]
INPUTS = ["audit/e7/e7_output", "audit/e8/e8_output", "audit/e9_runtime_pilot/e9_output"]
JSONL = ["think_ledger.jsonl", "compactions.jsonl"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inventory():
    files = {f"audit/compaction_thinking/{n}": HERE / n for n in OWN}
    for p in sorted((HERE / "validation").rglob("*")):
        if p.is_file():
            files[p.relative_to(ROOT).as_posix()] = p
    for d in INPUTS:
        for n in JSONL:
            files[f"{d}/{n}"] = ROOT / d / n
    return {k: sha(v) for k, v in sorted(files.items())}


def main():
    out = HERE / "FREEZE.json"
    if "--verify" in sys.argv:
        frozen = json.loads(out.read_text(encoding="utf-8"))["sha256"]
        now = inventory()
        bad = sorted(k for k in set(frozen) | set(now) if frozen.get(k) != now.get(k))
        print(f"{len(frozen)} files: " + ("ALL MATCH" if not bad else f"MISMATCH {bad}"))
        return 1 if bad else 0
    if out.exists():
        print("FREEZE.json exists; refusing to overwrite")
        return 1
    inv = inventory()
    out.write_text(json.dumps({"frozen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "n_files": len(inv), "sha256": inv}, indent=1), encoding="utf-8")
    print(f"FROZEN {len(inv)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
