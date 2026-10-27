"""Freeze a set of files before an experiment run, and verify them afterwards.

Writes a JSON manifest with the UTC freeze time and the SHA-256 of every listed file
(paths relative to the manifest's directory). Standard library only.

    python scripts/freeze_manifest.py freeze  MANIFEST.json  file1 file2 dir/...
    python scripts/freeze_manifest.py verify  MANIFEST.json

`verify` exits non-zero if any file is missing or changed.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expand(base: Path, items):
    for item in items:
        p = (base / item) if not Path(item).is_absolute() else Path(item)
        if p.is_dir():
            yield from sorted(q for q in p.rglob("*") if q.is_file())
        else:
            yield p


def freeze(manifest: Path, items):
    base = manifest.resolve().parent
    if manifest.exists():
        sys.exit(f"refusing to overwrite existing manifest {manifest.name}; write an amendment instead")
    files = {}
    for p in expand(base, items):
        rel = p.resolve().relative_to(base).as_posix()
        files[rel] = sha256(p)
    record = {"frozen_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "files": files}
    manifest.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"frozen {len(files)} files at {record['frozen_utc']}")


def verify(manifest: Path):
    base = manifest.resolve().parent
    record = json.loads(manifest.read_text(encoding="utf-8"))
    bad = []
    for rel, digest in record["files"].items():
        p = base / rel
        if not p.is_file():
            bad.append(f"MISSING {rel}")
        elif sha256(p) != digest:
            bad.append(f"CHANGED {rel}")
    for line in bad:
        print(line)
    print(f"{len(record['files']) - len(bad)}/{len(record['files'])} match (frozen {record['frozen_utc']})")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in {"freeze", "verify"}:
        sys.exit(__doc__)
    if sys.argv[1] == "freeze":
        freeze(Path(sys.argv[2]), sys.argv[3:])
    else:
        verify(Path(sys.argv[2]))
