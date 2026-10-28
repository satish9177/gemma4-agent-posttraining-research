#!/usr/bin/env python3
"""Prepare the frozen pilot sample for validation. Network: GitHub API and pinned Hugging Face datasets.

For every row of pilot_candidates.csv:
  * GitHub: base commit (PR base.sha, the SWE-bench convention), merge time, and the PR diff;
  * split the diff by file into a test patch (paths matching TEST_PATH) and a gold patch (everything else);
  * test files to run: added or modified .py files in the test patch named test_*.py / *_test.py, or inside a
    test directory (conftest.py and __init__.py excluded);
  * install recipe (deterministic, no model): the install_config of the most recently created published task
    for the same repository in SWE-rebench (V1) or the SWE-rebench monthly sets; if none exists, the generic
    recipe, with SWE-bench-Live's pytest command for the repository when one is published.

Output: data/pilot_tasks.jsonl (gitignored; its SHA-256 is frozen) and pilot_prepare_summary.json.
Selection is not changed here: every selected candidate is written, with any preparation failure recorded.

    GITHUB_TOKEN=<token> python -I analysis/tier_a_pilot/prepare_pilot.py
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import post_release_inventory as INV  # noqa: E402
import post_release_mining_feasibility as MF  # noqa: E402

TEST_PATH = MF.TEST_PATH
RUNNABLE = re.compile(r"(^|/)test_[^/]*\.py$|_test\.py$|(^|/)(tests?|testing)/.*\.py$", re.I)
NOT_RUNNABLE = re.compile(r"(^|/)(conftest|__init__)\.py$")
CACHE = HERE.parent / ".cache_inventory"
V1_REV = "89cdfbab4ab1bd8f5a658bb212d1b63624f4f881"


def gh(url, accept="application/vnd.github+json"):
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    delay = 5
    for _ in range(8):
        req = urllib.request.Request(url, headers={"Authorization": f"bearer {tok}", "Accept": accept,
                                                   "User-Agent": "tier-a-pilot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 500, 502, 503, 504):
                time.sleep(float(e.headers.get("retry-after") or delay)); delay = min(delay * 2, 300); continue
            return e.code, e.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(delay); delay = min(delay * 2, 300)
    return 0, b""


def split_diff(diff: str):
    chunks = re.split(r"(?m)^(?=diff --git )", diff)
    test, gold, test_files, deleted = [], [], [], []
    for c in chunks:
        if not c.startswith("diff --git "):
            continue
        m = re.match(r"diff --git a/(\S+) b/(\S+)", c)
        if not m:
            gold.append(c); continue
        a_path, b_path = m.group(1), m.group(2)
        is_deleted = "\n+++ /dev/null" in c or "\ndeleted file mode" in c
        path = a_path if is_deleted else b_path
        if TEST_PATH.search(path):
            test.append(c)
            if not is_deleted and path.endswith(".py") and RUNNABLE.search(path) and not NOT_RUNNABLE.search(path):
                test_files.append(path)
        else:
            gold.append(c)
    return "".join(test), "".join(gold), sorted(set(test_files))


def _plain(x):
    """Parquet values (numpy arrays, nested dicts) -> JSON-serializable Python values."""
    if hasattr(x, "tolist"):
        return _plain(x.tolist())
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    return x


def load_recipes():
    """canonical repo id -> list of (created_at, source, instance_id, install_config) and SWE-bench-Live test cmds."""
    import pandas as pd
    lb_src = INV.SOURCES[0]
    lb_meta = INV.hf_dataset_meta(lb_src["dataset_id"], lb_src["revision"])
    frames = []
    for split in sorted(lb_meta["split_files"]):
        for path in lb_meta["split_files"][split]:
            df, _ = INV.read_hf_parquet_columns(lb_meta["dataset_id"], lb_meta["revision_sha"], path,
                                                ["repo", "instance_id", "created_at", "install_config"], CACHE)
            df["source"] = "swe_rebench_monthly"
            frames.append(df)
    for path in ["data/test-00000-of-00002.parquet", "data/test-00001-of-00002.parquet"]:
        df, _ = INV.read_hf_parquet_columns("nebius/SWE-rebench", V1_REV, path,
                                            ["repo", "instance_id", "created_at", "install_config"], CACHE)
        df["source"] = "swe_rebench_v1"
        frames.append(df)
    rec = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["instance_id"])
    rec["created_at_utc"] = INV.to_utc(rec["created_at"])
    sbl_src = INV.SOURCES[1]
    sbl_meta = INV.hf_dataset_meta(sbl_src["dataset_id"], sbl_src["revision"])
    sframes = []
    for path in sbl_meta["split_files"]["full"]:
        df, _ = INV.read_hf_parquet_columns(sbl_meta["dataset_id"], sbl_meta["revision_sha"], path,
                                            ["repo", "instance_id", "created_at", "test_cmds"], CACHE)
        sframes.append(df)
    sbl = pd.concat(sframes, ignore_index=True)
    sbl["created_at_utc"] = INV.to_utc(sbl["created_at"])
    return rec, sbl


def main():
    rows = [r for r in csv.DictReader(l for l in open(HERE / "pilot_candidates.csv", encoding="utf-8")
                                      if not l.startswith("#"))]
    rec, sbl = load_recipes()
    names = set(rec["repo"].map(INV.norm_repo)) | set(sbl["repo"].map(INV.norm_repo)) | {r["repo"].lower() for r in rows}
    meta = MF.repo_meta(names, CACHE)   # served from the mining cache; follows renames via numeric ids
    rid = lambda n: (meta.get(INV.norm_repo(n)) or {}).get("id")  # noqa: E731
    rec["rid"] = rec["repo"].map(rid)
    sbl["rid"] = sbl["repo"].map(rid)
    out, summary = [], {"selected": len(rows), "pr_fetched": 0, "diff_fetched": 0, "has_test_patch": 0,
                        "has_gold_patch": 0, "has_runnable_test_file": 0, "recipe_source": {}}
    data = HERE / "data"
    data.mkdir(exist_ok=True)
    for r in rows:
        repo, num = r["repo"], int(r["pr_number"])
        t = {"pilot_id": r["pilot_id"], "repo": repo, "pr_number": num, "pr_url": r["pr_url"], "prep_error": None}
        st, body = gh(f"https://api.github.com/repos/{repo}/pulls/{num}")
        if st != 200:
            t["prep_error"] = f"pull request API HTTP {st}"
        else:
            pr = json.loads(body)
            summary["pr_fetched"] += 1
            t.update(base_sha=pr["base"]["sha"], base_ref=pr["base"]["ref"], merged_at=pr["merged_at"],
                     merge_commit_sha=pr["merge_commit_sha"], clone_url=pr["base"]["repo"]["clone_url"],
                     license_now=((pr["base"]["repo"].get("license") or {}).get("spdx_id")))
            st, body = gh(f"https://api.github.com/repos/{repo}/pulls/{num}", accept="application/vnd.github.diff")
            if st != 200:
                t["prep_error"] = f"diff API HTTP {st}"
            else:
                summary["diff_fetched"] += 1
                test_patch, gold_patch, test_files = split_diff(body.decode("utf-8", errors="replace"))
                t.update(test_patch=test_patch, gold_patch=gold_patch, test_files=test_files,
                         test_patch_sha256=hashlib.sha256(test_patch.encode()).hexdigest(),
                         gold_patch_sha256=hashlib.sha256(gold_patch.encode()).hexdigest())
                summary["has_test_patch"] += bool(test_patch)
                summary["has_gold_patch"] += bool(gold_patch)
                summary["has_runnable_test_file"] += bool(test_files)
        # recipe
        cid = rid(repo)
        cands = rec[(rec["rid"] == cid) & rec["install_config"].map(lambda c: c is not None and len(c) > 0)]
        recipe = {"source": "generic", "instance_id": None, "created_at": None, "install_config": None,
                  "sbl_test_cmds": None}
        if len(cands):
            best = cands.sort_values(["created_at_utc", "instance_id"]).iloc[-1]
            cfg = best["install_config"]
            cfg = json.loads(cfg) if isinstance(cfg, str) else _plain(cfg)
            recipe.update(source=best["source"], instance_id=best["instance_id"],
                          created_at=best["created_at_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"), install_config=cfg)
        s = sbl[sbl["rid"] == cid]
        if len(s):
            b = s.sort_values(["created_at_utc", "instance_id"]).iloc[-1]
            recipe["sbl_test_cmds"] = _plain(b["test_cmds"])
            recipe["sbl_instance_id"] = b["instance_id"]
        t["recipe"] = recipe
        summary["recipe_source"][recipe["source"]] = summary["recipe_source"].get(recipe["source"], 0) + 1
        out.append(t)
        time.sleep(0.3)
    with open(data / "pilot_tasks.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for t in out:
            f.write(json.dumps(t, sort_keys=True, default=str) + "\n")
    summary["pilot_tasks_sha256"] = hashlib.sha256((data / "pilot_tasks.jsonl").read_bytes()).hexdigest()
    (HERE / "pilot_prepare_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
