#!/usr/bin/env python3
"""Build harness-development tasks: published post-release tasks with KNOWN fail-to-pass lists, from repositories
that are NOT in the pilot sample. Used only to check the validation harness before the pilot is frozen.

Rule (fixed): published SWE-rebench monthly tasks created 2026-04-02 .. 2026-05-12, repository not in the pilot
sample and not a development repository, one per repository, first N_DEV by instance_id.

    python -I analysis/tier_a_pilot/harness_dev_tasks.py
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import post_release_inventory as INV  # noqa: E402
import prepare_pilot as PP  # noqa: E402

N_DEV = 4
DEV_REPOS = {"fastapi/fastapi", "textualize/rich", "psf/requests", "encode/httpx"}


def main():
    pilot_repos = {r["repo"].lower() for r in csv.DictReader(
        l for l in open(HERE / "pilot_candidates.csv", encoding="utf-8") if not l.startswith("#"))}
    src = INV.SOURCES[0]
    meta = INV.hf_dataset_meta(src["dataset_id"], src["revision"])
    path = meta["split_files"]["2026_03"][0]
    cols = ["repo", "instance_id", "created_at", "base_commit", "patch", "test_patch", "install_config",
            "FAIL_TO_PASS", "PASS_TO_PASS"]
    df, _ = INV.read_hf_parquet_columns(meta["dataset_id"], meta["revision_sha"], path, cols, PP.CACHE)
    df["created_at_utc"] = INV.to_utc(df["created_at"])
    df = df[(df["created_at_utc"] >= "2026-04-02") & ~df["instance_id"].str.endswith("_interface")]
    df = df[~df["repo"].str.lower().isin(pilot_repos | DEV_REPOS)].sort_values("instance_id")
    df = df.drop_duplicates(subset=["repo"]).head(N_DEV)
    out = []
    import time as _t
    for i, r in enumerate(df.itertuples(), 1):
        st, body = PP.gh(f"https://api.github.com/repos/{r.repo}/pulls/{int(PP.re.search(r'-(\d+)$', r.instance_id).group(1))}")
        merged_at = json.loads(body)["merged_at"] if st == 200 else None
        _t.sleep(0.3)
        _, _, test_files = PP.split_diff(r.test_patch)
        cfg = PP._plain(r.install_config)
        out.append({"pilot_id": f"D{i:02d}", "repo": r.repo, "pr_number": int(PP.re.search(r"-(\d+)$", r.instance_id).group(1)),
                    "instance_id": r.instance_id, "prep_error": None, "clone_url": f"https://github.com/{r.repo}.git",
                    "base_sha": r.base_commit, "test_patch": r.test_patch, "gold_patch": r.patch, "test_files": test_files,
                    "license_now": "MIT", "merged_at": merged_at, "recipe": {"source": "own_published_config", "install_config": cfg},
                    "published_F2P": PP._plain(r.FAIL_TO_PASS), "published_P2P_count": len(PP._plain(r.PASS_TO_PASS))})
    (HERE / "runs").mkdir(exist_ok=True)
    with open(HERE / "runs" / "dev_tasks.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for t in out:
            f.write(json.dumps(t, default=str) + "\n")
    for t in out:
        print(t["pilot_id"], t["instance_id"], len(t["test_files"]), "files;", len(t["published_F2P"]), "published F2P")


if __name__ == "__main__":
    main()
