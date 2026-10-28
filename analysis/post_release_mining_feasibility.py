#!/usr/bin/env python3
"""Mining-feasibility stage for the two evaluation tiers. CPU and network only.

No model is run and no model output is read, so no candidate is selected on any model's
performance. Tier rules are documented in analysis/post_release_mining_plan.md.

Tier A (primary, strict post-release)
    How many merged, issue-linked Python pull requests, created after the last published
    post-release data (2026-05-12) and merged before the as-of day, pass SWE-rebench's
    deterministic candidate filters in repositories that are open-licensed, outside the
    training pool and outside the development repositories? How many valid tasks could
    they plausibly yield?

    Two measurements:
    * a COMPLETE enumeration inside the known-buildable universe: repositories in which an
      open pipeline has already built a working environment for at least one task
      (SWE-rebench, SWE-rebench-leaderboard, SWE-bench-Live);
    * a seeded RANDOM-HOUR SAMPLE of all GitHub Python repositories, to size the rest.

    Yield is calibrated on the window where the answer is known: the published
    post-release tasks created 2026-04-02 .. 2026-05-12.

Tier B (secondary, post-pretraining-cutoff, pre-release)
    How many published tasks with an environment were created after the January 2025
    pretraining cutoff and before the 2026-04-02 release, in open-licensed repositories
    outside the training pool and the development repositories?

Usage
    GITHUB_TOKEN=<token> python -I analysis/post_release_mining_feasibility.py

    A token is needed only for GitHub requests that are not already cached. It is read from
    GITHUB_TOKEN or GH_TOKEN, sent only to api.github.com, and never printed or stored.
    Every GitHub answer is cached (compacted) under <cache>/_mining/, so a re-run with the
    same cache reproduces the outputs exactly. Downloaded data are parsed, never executed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import post_release_inventory as INV  # noqa: E402  (dataset readers and pinned revisions)

# ---------------------------------------------------------------------------
# Frozen parameters
# ---------------------------------------------------------------------------
RELEASE = dt.datetime(2026, 4, 2, tzinfo=dt.timezone.utc)                     # Gemma 4 public release
PUBLISHED_END = dt.datetime(2026, 5, 12, 23, 59, 59, tzinfo=dt.timezone.utc)  # end of published post-release data
MINING_START = dt.datetime(2026, 5, 13, tzinfo=dt.timezone.utc)
TIER_B_START = dt.datetime(2025, 2, 1, tzinfo=dt.timezone.utc)                # after the January 2025 pretraining cutoff
DEFAULT_AS_OF = "2026-10-27"                       # PRs created before and merged before this UTC day

SEED = 20261027
HOURS_W1 = 24           # random hours sampled from the mining window
HOURS_W0 = 12           # random hours sampled from the calibration window
BOOTSTRAP_REPS = 2000
PER_REPO_CAP = 10       # sensitivity row only; the frozen mining specification fixes the final cap
REPOS_PER_QUERY = 30
DETAIL_BATCH, DETAIL_WORKERS = 25, 4

# SWE-rebench preliminary candidate filters (arXiv 2505.20411, section 2):
MIN_PYTHON_SHARE = 0.75          # Python share of the code (GitHub language bytes as a proxy for lines)
MIN_ISSUE_CHARS = 11             # issue description longer than 10 characters
FILES_MIN, FILES_MAX = 1, 15     # files changed by the PR
# SWE-rebench benchmark-subset filters that can be checked before building (appendix H):
LB_MAX_NONTEST_FILES = 3
LB_ISSUE_WORDS = (16, 1000)
# Published full-pipeline yield: 21,336 valid tasks from about 153,400 filtered candidates.
PAPER_YIELD = {"valid": 21336, "candidates": 153400}
GOLD_PRIOR = INV.GOLD_VALIDATION_PRIOR   # our own re-validation keep rate on already-validated tasks (101/115)
TARGETS = (200, 250)
PUBLISHED_TIER_A = 62                    # published post-release candidates (post_release_task_inventory.md)

# Repositories used to develop the scaffold and its prompts. Excluded from both tiers.
DEV_REPOS = ["fastapi/fastapi", "Textualize/rich", "psf/requests", "encode/httpx"]

TEST_PATH = re.compile(r"(^|/)(tests?|testing|e2e)(/|$)|(^|/)test_[^/]*$|_tests?\.py$|(^|/)conftest\.py$", re.I)
INSTANCE = re.compile(r"^(?P<repo>.+?)-(?P<num>\d+)(?:_interface)?$")
NATIVE_MARKERS = {"cmakelists.txt", "cargo.toml", "meson.build", "binding.gyp", "build.rs"}
PACKAGING = {"pyproject.toml", "setup.py", "setup.cfg"}

API = "https://api.github.com"
UA = "post-release-mining-feasibility/1.1 (research; stdlib urllib)"
STATS: Counter = Counter()
_LOCK = threading.Lock()

REPO_FIELDS = ("databaseId nameWithOwner isFork isArchived stargazerCount licenseInfo{spdxId} defaultBranchRef{name} "
               "languages(first:6, orderBy:{field:SIZE, direction:DESC}){ totalSize edges{ size node{name} } }")
DETAIL_QUERY = """query($ids:[ID!]!){ rateLimit{cost remaining resetAt}
  nodes(ids:$ids){ ... on PullRequest { id number changedFiles baseRefName
    closingIssuesReferences(first:3){ totalCount nodes{ number createdAt closed title bodyText repository{databaseId} } }
    files(first:20){ totalCount nodes{ path } } } } }"""
COUNT_QUERY = "query($q:String!){ rateLimit{cost remaining resetAt} search(query:$q, type:ISSUE, first:1){ issueCount } }"


def log(*x):
    print(*x, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# GitHub access with a compact on-disk cache
# ---------------------------------------------------------------------------

def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        sys.exit("A GitHub token is needed for uncached requests: set GITHUB_TOKEN (e.g. from `gh auth token`).")
    return tok


def _count(key, n=1):
    with _LOCK:
        STATS[key] += n


def _http(url: str, body: bytes | None = None) -> dict:
    delay = 5.0
    for _ in range(12):
        req = urllib.request.Request(url, data=body, method="POST" if body else "GET", headers={
            "Authorization": f"bearer {_token()}", "User-Agent": UA, "Accept": "application/vnd.github+json",
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            _count(f"http_{e.code}")
            if e.code in (403, 429, 500, 502, 503, 504):
                wait = e.headers.get("retry-after")
                reset = e.headers.get("x-ratelimit-reset")
                if wait:
                    pause = float(wait)
                elif e.headers.get("x-ratelimit-remaining") == "0" and reset:
                    pause = max(1.0, float(reset) - time.time() + 2)
                else:
                    pause = delay
                time.sleep(min(pause, 900))
                delay = min(delay * 2, 300)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            _count("network_retry")
            time.sleep(delay)
            delay = min(delay * 2, 300)
    raise RuntimeError(f"GitHub request failed repeatedly: {url.split('?')[0]}")


def gql(query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    delay = 5.0
    for _ in range(8):
        out = _http(f"{API}/graphql", body)
        errs = [e for e in out.get("errors") or [] if e.get("type") != "NOT_FOUND"]
        if errs:
            _count("graphql_retry")
            time.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        rl = (out.get("data") or {}).get("rateLimit") or {}
        _count("graphql_requests")
        _count("graphql_cost", int(rl.get("cost") or 0))
        if rl and int(rl.get("remaining", 5000)) < 200:
            reset = dt.datetime.fromisoformat(rl["resetAt"].replace("Z", "+00:00"))
            time.sleep(max(0.0, (reset - dt.datetime.now(dt.timezone.utc)).total_seconds()) + 5)
        time.sleep(0.5)
        return out["data"]
    raise RuntimeError("GitHub GraphQL request kept returning errors")


def cached(cache: Path, kind: str, key_obj, fetch):
    key = hashlib.sha1(json.dumps(key_obj, sort_keys=True).encode()).hexdigest()[:20]
    p = cache / "_mining" / kind / f"{key}.json"
    if p.exists():
        _count("cache_hits")
        return json.loads(p.read_text(encoding="utf-8"))
    val = fetch()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(val), encoding="utf-8")
    os.replace(tmp, p)
    return val


# ---------------------------------------------------------------------------
# Repository metadata in batches (follows renames; numeric ids make matching robust)
# ---------------------------------------------------------------------------

def _repo_rec(r: dict, with_tree: bool) -> dict:
    langs = r.get("languages") or {}
    total = langs.get("totalSize") or 0
    py = sum(e["size"] for e in langs.get("edges") or [] if e["node"]["name"] == "Python")
    rec = {"id": r["databaseId"], "name": r["nameWithOwner"], "fork": r["isFork"], "archived": r["isArchived"],
           "stars": r["stargazerCount"], "spdx": (r.get("licenseInfo") or {}).get("spdxId"),
           "default_branch": (r.get("defaultBranchRef") or {}).get("name"),
           "python_share": round(py / total, 4) if total else 0.0}
    if with_tree:
        rec["tree"] = sorted(e["name"] for e in ((r.get("object") or {}).get("entries") or []))
    return rec


def repo_meta(names, cache: Path, with_tree: bool = False) -> dict[str, dict | None]:
    """lower-case owner/name -> metadata (None if the repository no longer resolves)."""
    names = sorted({INV.norm_repo(n) for n in names if "/" in str(n)})
    batch = 25 if with_tree else 50
    chunks = [names[i:i + batch] for i in range(0, len(names), batch)]

    def one(chunk):
        def fetch():
            tree = ' object(expression:"HEAD:"){ ... on Tree { entries { name } } }' if with_tree else ""
            parts = [f"r{j}: repository(owner:{json.dumps(n.split('/', 1)[0])}, name:{json.dumps(n.split('/', 1)[1])})"
                     f"{{ {REPO_FIELDS}{tree} }}" for j, n in enumerate(chunk)]
            data = gql("query{ rateLimit{cost remaining resetAt} " + " ".join(parts) + " }", {})
            return {n: (_repo_rec(data[f"r{j}"], with_tree) if data.get(f"r{j}") else None) for j, n in enumerate(chunk)}
        return cached(cache, "repo_tree" if with_tree else "repo_meta", chunk, fetch)

    out: dict[str, dict | None] = {}
    with ThreadPoolExecutor(DETAIL_WORKERS) as ex:
        for k, res in enumerate(ex.map(one, chunks)):
            out.update(res)
            if k % 20 == 0:
                log(f"  repo metadata batch {k + 1}/{len(chunks)}")
    return out


# ---------------------------------------------------------------------------
# PR search (REST search: max 1,000 results per query, so windows are split adaptively)
# ---------------------------------------------------------------------------

def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _search_page(q: str, page: int, cache: Path) -> dict:
    def fetch():
        for _ in range(3):
            url = f"{API}/search/issues?" + urllib.parse.urlencode(
                {"q": q, "per_page": 100, "page": page, "sort": "created", "order": "asc"})
            d = _http(url)
            _count("search_requests")
            time.sleep(2.1)  # search API: 30 requests per minute
            if not d.get("incomplete_results"):
                break
            _count("search_incomplete_retry")
        else:
            _count("search_incomplete_kept")
        rows = [{"node_id": it["node_id"], "number": it["number"], "created": it["created_at"],
                 "merged": (it.get("pull_request") or {}).get("merged_at"),
                 "repo": it["repository_url"].split("/repos/", 1)[1]} for it in d.get("items", [])]
        return {"total": d.get("total_count", 0), "incomplete": bool(d.get("incomplete_results")), "rows": rows}
    return cached(cache, "search", [q, page], fetch)


def search_window(base_q: str, start: dt.datetime, end: dt.datetime, as_of: str, cache: Path) -> list[dict]:
    q = f"{base_q} created:{_iso(start)}..{_iso(end)} merged:<{as_of}"
    first = _search_page(q, 1, cache)
    if first["total"] > 1000 and (end - start) > dt.timedelta(minutes=10):
        mid = (start + (end - start) / 2).replace(microsecond=0)
        return (search_window(base_q, start, mid, as_of, cache)
                + search_window(base_q, mid + dt.timedelta(seconds=1), end, as_of, cache))
    if first["total"] > 1000:
        _count("windows_truncated_at_1000")
    rows = list(first["rows"])
    for page in range(2, min(10, math.ceil(first["total"] / 100)) + 1):
        rows.extend(_search_page(q, page, cache)["rows"])
    _count("search_windows")
    return rows


def search_count(q: str, cache: Path) -> int:
    return cached(cache, "count", q, lambda: gql(COUNT_QUERY, {"q": q})["search"]["issueCount"])


def pr_details(node_ids: list[str], cache: Path) -> dict[str, dict]:
    ids = sorted(set(node_ids))
    batches = [ids[i:i + DETAIL_BATCH] for i in range(0, len(ids), DETAIL_BATCH)]

    def one(batch):
        def fetch():
            res = {}
            for n in gql(DETAIL_QUERY, {"ids": batch})["nodes"]:
                if not n or "id" not in n:
                    continue
                ci = n.get("closingIssuesReferences") or {}
                issues = [{"number": x["number"], "created": x["createdAt"], "closed": x["closed"],
                           "repo_id": (x.get("repository") or {}).get("databaseId"),
                           "body_chars": len((x.get("bodyText") or "").strip()),
                           "words": len(((x.get("title") or "") + " " + (x.get("bodyText") or "")).split())}
                          for x in ci.get("nodes") or []]
                f = n.get("files") or {}
                res[n["id"]] = {"changed_files": n["changedFiles"], "base": n["baseRefName"],
                                "n_issues": ci.get("totalCount", 0), "issues": issues,
                                "n_files_listed": f.get("totalCount", 0),
                                "files": [x["path"] for x in f.get("nodes") or []]}
            return res
        return cached(cache, "details", batch, fetch)

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(DETAIL_WORKERS) as ex:
        for k, res in enumerate(ex.map(one, batches)):
            out.update(res)
            if k % 100 == 0:
                log(f"  PR details batch {k + 1}/{len(batches)}")
    return out


# ---------------------------------------------------------------------------
# Candidate filters
# ---------------------------------------------------------------------------

def is_test(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def license_ok(spdx: str | None, repo: str) -> bool:
    if spdx in INV.OPEN_LICENSES:
        return True
    return INV.norm_repo(repo) in INV.MANUAL_LICENSE_REVIEW and spdx in (None, "NOASSERTION", "OTHER")


REPO_STEPS = ["repository_resolves", "outside_development_repos", "outside_training_pool", "not_fork_or_archived",
              "python_share_ge_75", "open_license"]
PR_STEPS = ["details_retrieved", "merged_into_default_branch", "one_closing_issue_same_repo", "issue_closed",
            "issue_text_gt_10_chars", "files_1_to_15", "touches_tests", "touches_non_test_python"]


def repo_flag(step: str, m: dict | None, train_ids: set, dev_ids: set) -> bool:
    if step == "repository_resolves":
        return m is not None
    return {"outside_development_repos": m["id"] not in dev_ids,
            "outside_training_pool": m["id"] not in train_ids,
            "not_fork_or_archived": not m["fork"] and not m["archived"],
            "python_share_ge_75": m["python_share"] >= MIN_PYTHON_SHARE,
            "open_license": license_ok(m["spdx"], m["name"])}[step]


def pr_flag(step: str, r: dict) -> bool:
    d, m = r.get("d"), r["m"]
    if step == "details_retrieved":
        return d is not None
    iss = d["issues"][0] if d["issues"] else None
    files = d["files"]
    return {
        "merged_into_default_branch": d["base"] == m["default_branch"],
        "one_closing_issue_same_repo": d["n_issues"] == 1 and iss is not None and iss["repo_id"] == m["id"],
        "issue_closed": bool(iss and iss["closed"]),
        "issue_text_gt_10_chars": bool(iss and iss["body_chars"] >= MIN_ISSUE_CHARS),
        "files_1_to_15": FILES_MIN <= d["changed_files"] <= FILES_MAX and d["n_files_listed"] == len(files),
        "touches_tests": any(is_test(f) for f in files),
        "touches_non_test_python": any(not is_test(f) and f.endswith(".py") for f in files),
    }[step]


def run_funnel(rows: list[dict], meta: dict, train_ids: set, dev_ids: set, cache: Path):
    """Apply the filters in order; PR details are fetched only for PRs that pass the repository filters."""
    seen, alive = set(), []
    for r in rows:
        if r["node_id"] not in seen:
            seen.add(r["node_id"])
            alive.append(dict(r, m=meta.get(INV.norm_repo(r["repo"]))))
    table = [{"step": "merged, issue-linked PRs returned by search", "prs": len(alive),
              "repos": len({INV.norm_repo(r["repo"]) for r in alive})}]
    for step in REPO_STEPS:
        alive = [r for r in alive if repo_flag(step, r["m"], train_ids, dev_ids)]
        table.append({"step": step, "prs": len(alive), "repos": len({r["m"]["id"] for r in alive})})
    det = pr_details([r["node_id"] for r in alive], cache)
    for r in alive:
        r["d"] = det.get(r["node_id"])
    for step in PR_STEPS:
        alive = [r for r in alive if pr_flag(step, r)]
        table.append({"step": step, "prs": len(alive), "repos": len({r["m"]["id"] for r in alive})})
    for r in alive:
        files, iss = r["d"]["files"], r["d"]["issues"][0]
        nontest = [f for f in files if not is_test(f)]
        r.update(test_files=sum(map(is_test, files)), non_test_files=len(nontest), issue=iss,
                 issue_post_release=_dt(iss["created"]) >= RELEASE,
                 leaderboard_shape=len(nontest) <= LB_MAX_NONTEST_FILES
                 and LB_ISSUE_WORDS[0] <= iss["words"] <= LB_ISSUE_WORDS[1])
    return table, alive


def _dt(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def env_class(rec: dict | None, known: bool) -> str:
    if known:
        return "A_known_buildable"
    tree = {t.lower() for t in (rec or {}).get("tree", [])}
    if not tree & PACKAGING:
        return "D_no_root_packaging"
    if tree & NATIVE_MARKERS:
        return "C_packaging_with_native_build"
    return "B_standard_packaging"


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def bootstrap_total(per_hour: list[int], n_hours_total: int, rng: random.Random) -> dict:
    k = len(per_hour)
    if k == 0:
        return {"estimate": None, "ci95": None}
    est = sum(per_hour) / k * n_hours_total
    reps = sorted(sum(rng.choice(per_hour) for _ in range(k)) / k * n_hours_total for _ in range(BOOTSTRAP_REPS))
    return {"estimate": round(est), "ci95": [round(reps[int(0.025 * BOOTSTRAP_REPS)]),
                                             round(reps[int(0.975 * BOOTSTRAP_REPS) - 1])]}


def wilson(k: int, n: int) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    k = min(k, n)
    z, p = 1.959964, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def capped(rows: list[dict], cap: int) -> int:
    return sum(min(v, cap) for v in Counter(r["m"]["id"] for r in rows).values())


# ---------------------------------------------------------------------------
# Published data
# ---------------------------------------------------------------------------

def load_datasets(cache: Path):
    import pandas as pd
    frames = {}
    for src in INV.SOURCES[:2]:
        meta = INV.hf_dataset_meta(src["dataset_id"], src["revision"])
        raw, _, _ = INV.load_source(src, meta, cache, False)
        frames[src["key"]] = (raw, meta["revision_sha"])
    T = INV.TRAIN_POOL
    tm = INV.hf_dataset_meta(T["dataset_id"], T["revision"])
    tr, _ = INV.read_hf_parquet_columns(tm["dataset_id"], tm["revision_sha"], tm["split_files"][T["split"]][0],
                                        T["columns"], cache)
    tr = tr[tr[T["language_column"]].astype(str).str.lower() == T["language_value"]].copy()
    tr["repo_norm"] = tr["repo"].map(INV.norm_repo)
    tr["created_at_utc"] = INV.to_utc(tr["created_at"])
    v1_rev = "89cdfbab4ab1bd8f5a658bb212d1b63624f4f881"   # nebius/SWE-rebench (V1), pinned
    parts = []
    for p in ["data/test-00000-of-00002.parquet", "data/test-00001-of-00002.parquet"]:
        df, _ = INV.read_hf_parquet_columns("nebius/SWE-rebench", v1_rev, p,
                                            ["repo", "instance_id", "created_at", "docker_image"], cache)
        parts.append(df)
    v1 = pd.concat(parts, ignore_index=True)
    v1["repo_norm"] = v1["repo"].map(INV.norm_repo)
    v1["created_at_utc"] = INV.to_utc(v1["created_at"])
    v1["has_env"] = v1["docker_image"].map(INV._nonempty)
    return frames, (tr, tm["revision_sha"]), (v1, v1_rev)


def _num(instance_id: str) -> int:
    m = INSTANCE.match(instance_id)
    return int(m.group("num")) if m else -1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    global HOURS_W1, HOURS_W0
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache-dir", default=os.environ.get("INVENTORY_CACHE_DIR", str(HERE / ".cache_inventory")))
    ap.add_argument("--as-of", default=DEFAULT_AS_OF, help="UTC day: PRs created and merged before it")
    ap.add_argument("--out-json", default=str(HERE / "post_release_mining_feasibility.json"))
    ap.add_argument("--out-csv", default=str(HERE / "tier_a_mining_candidates.csv"))
    ap.add_argument("--tier-b-csv", default=str(HERE / "tier_b_candidates.csv"))
    ap.add_argument("--smoke", action="store_true", help="tiny run (2 hours per window, 60 repos) to test the code")
    a = ap.parse_args(argv)
    if a.smoke:
        HOURS_W1, HOURS_W0 = 2, 2
    cache = Path(a.cache_dir)
    as_of = dt.datetime.strptime(a.as_of, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    w1 = (MINING_START, as_of - dt.timedelta(seconds=1))
    w0 = (RELEASE, PUBLISHED_END)
    rng = random.Random(SEED)

    # --- published data and repository resolution ---------------------------------------------
    frames, (train, train_rev), (v1, v1_rev) = load_datasets(cache)
    lb, lb_rev = frames["swe_rebench_leaderboard"]
    sbl, sbl_rev = frames["swe_bench_live"]
    # The 'test' split is the union of the monthly splits, so rows repeat: keep one row per instance.
    lb_py = lb[lb["is_python"] & lb["has_env"]].drop_duplicates(subset=["instance_id"]).copy()
    option_b = json.loads((HERE / "post_release_inventory.json").read_text(encoding="utf-8"))[
        "overlap_with_v2_python"]["overlapping_repo_names"]
    universe_names = set(lb_py["repo_norm"]) | set(sbl["repo_norm"]) | set(v1["repo_norm"])
    log("resolving repositories ...")
    meta = repo_meta(universe_names | set(train["repo_norm"]) | set(map(INV.norm_repo, DEV_REPOS)) | set(option_b),
                     cache)
    rid = lambda n: (meta.get(INV.norm_repo(n)) or {}).get("id")  # noqa: E731
    option_b_ids = {rid(n) for n in option_b} - {None}
    train["rid"] = train["repo_norm"].map(rid)
    train_all_ids = set(train["rid"].dropna().astype(int))
    train_ids = train_all_ids - option_b_ids                      # training pool after Option B
    dev_ids = {rid(n) for n in DEV_REPOS} - {None}
    kept = train[~train["rid"].isin(option_b_ids)]
    option_b_check = {"v2_python_tasks_before": len(train), "v2_python_repos_before": int(train["repo_norm"].nunique()),
                      "removed_repos_resolved": len(option_b_ids), "tasks_after": len(kept),
                      "repos_after": int(kept["repo_norm"].nunique()),
                      "v2_python_repos_not_resolving_on_github": int(train[train["rid"].isna()]["repo_norm"].nunique())}

    K_ids = {rid(n) for n in universe_names} - {None}
    K_elig = K_ids - train_ids - dev_ids
    pre_names = set(v1["repo_norm"]) | set(sbl["repo_norm"]) | set(lb_py[lb_py["created_at_utc"] < RELEASE]["repo_norm"])
    K_pre_elig = ({rid(n) for n in pre_names} - {None}) - train_ids - dev_ids
    id_name = {v["id"]: v["name"] for v in meta.values() if v}
    log(f"known-buildable: {len(K_ids)} repos, {len(K_elig)} eligible; pre-window eligible {len(K_pre_elig)}")

    # --- global top-of-funnel counts --------------------------------------------------------------
    base_global = "is:pr is:merged linked:issue language:Python"
    monthly, t = {}, RELEASE
    while t <= w1[1]:
        nxt = (t.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        end = min(nxt - dt.timedelta(seconds=1), w1[1])
        monthly[t.strftime("%Y-%m")] = search_count(f"{base_global} created:{_iso(t)}..{_iso(end)} merged:<{a.as_of}", cache)
        t = nxt
    count_w1 = search_count(f"{base_global} created:{_iso(w1[0])}..{_iso(w1[1])} merged:<{a.as_of}", cache)
    count_w0 = search_count(f"{base_global} created:{_iso(w0[0])}..{_iso(w0[1])} merged:<{a.as_of}", cache)

    # --- global random-hour samples ------------------------------------------------------------
    samples = {}
    for label, win, k in (("W1", w1, HOURS_W1), ("W0", w0, HOURS_W0)):
        n_hours = int((win[1] - win[0]).total_seconds() // 3600)
        starts = [win[0] + dt.timedelta(hours=h) for h in sorted(rng.sample(range(n_hours), k))]
        per_hour = []
        for i, h in enumerate(starts):
            log(f"global sample {label}: hour {i + 1}/{k} ({h:%Y-%m-%d %H}:00Z)")
            per_hour.append(search_window(base_global, h, h + dt.timedelta(seconds=3599), a.as_of, cache))
        samples[label] = (n_hours, starts, per_hour)
    sample_repos = {r["repo"] for _, _, ph in samples.values() for rows in ph for r in rows}
    log(f"resolving {len(sample_repos)} sampled repositories ...")
    meta.update(repo_meta({INV.norm_repo(x) for x in sample_repos} - set(meta), cache))

    # --- known-buildable universe: complete enumeration ---------------------------------------
    def enumerate_universe(ids: set, win, label):
        names = sorted(id_name[i] for i in ids)
        if a.smoke:
            names = names[:60]
        def group(grp):
            try:
                return search_window("is:pr is:merged linked:issue " + " ".join(f"repo:{n}" for n in grp),
                                     win[0], win[1], a.as_of, cache)
            except urllib.error.HTTPError as e:   # 422: a repository in the group cannot be searched
                if e.code != 422:
                    raise
                if len(grp) == 1:
                    _count("repos_not_searchable")
                    return []
                return group(grp[:len(grp) // 2]) + group(grp[len(grp) // 2:])

        rows = []
        for i in range(0, len(names), REPOS_PER_QUERY):
            grp = names[i:i + REPOS_PER_QUERY]
            log(f"universe {label}: repos {i + 1}-{i + len(grp)} of {len(names)}")
            rows += group(grp)
        return [r for r in rows if rid(r["repo"]) in ids]

    k_w1 = enumerate_universe(K_elig, w1, "W1")
    k_w0 = enumerate_universe(K_pre_elig, w0, "W0")

    # --- filters ------------------------------------------------------------------------------
    log("filtering ...")
    f_k_w1, cand_k_w1 = run_funnel(k_w1, meta, train_ids, dev_ids, cache)
    f_k_w0, cand_k_w0 = run_funnel(k_w0, meta, train_ids, dev_ids, cache)
    sample_out, sample_cand_w1 = {}, []
    for label, (n_hours, starts, per_hour) in samples.items():
        flat = [r for rows in per_hour for r in rows]
        ftab, cand = run_funnel(flat, meta, train_ids, dev_ids, cache)
        keys = {r["node_id"] for r in cand}
        outside = {r["node_id"] for r in cand if r["m"]["id"] not in K_ids}
        outside100 = {r["node_id"] for r in cand if r["m"]["id"] not in K_ids and r["m"]["stars"] >= 100}
        if label == "W1":
            sample_cand_w1 = cand
        sample_out[label] = {
            "hours_in_window": n_hours, "hours_sampled": len(starts),
            "sampled_hour_starts_utc": [_iso(h) for h in starts],
            "prs_in_sampled_hours": len(flat), "funnel": ftab,
            "stage1_candidates_in_sample": len(cand),
            "stage1_candidates_in_sample_known_buildable": len(keys) - len(outside),
            "estimated_stage1_candidates_in_window": bootstrap_total(
                [sum(r["node_id"] in keys for r in rows) for rows in per_hour], n_hours, rng),
            "estimated_stage1_candidates_outside_known_buildable": bootstrap_total(
                [sum(r["node_id"] in outside for r in rows) for rows in per_hour], n_hours, rng),
            "estimated_stage1_candidates_outside_known_buildable_ge_100_stars": bootstrap_total(
                [sum(r["node_id"] in outside100 for r in rows) for rows in per_hour], n_hours, rng),
            "candidates_by_star_band": dict(sorted(Counter(
                "<10" if r["m"]["stars"] < 10 else "10-99" if r["m"]["stars"] < 100
                else "100-999" if r["m"]["stars"] < 1000 else ">=1000" for r in cand).items())),
        }

    # --- environment-feasibility proxy ------------------------------------------------------------
    trees = repo_meta({r["m"]["name"] for r in cand_k_w1 + sample_cand_w1}, cache, with_tree=True)
    for r in cand_k_w1 + sample_cand_w1:
        r["env_class"] = env_class(trees.get(INV.norm_repo(r["m"]["name"])), r["m"]["id"] in K_ids)
    sample_out["W1"]["stage1_candidates_env_class"] = dict(sorted(Counter(r["env_class"] for r in sample_cand_w1).items()))

    # --- calibration on the published window ----------------------------------------------------
    lb_w0 = lb_py[(lb_py["created_at_utc"] >= RELEASE) & (lb_py["created_at_utc"] <= PUBLISHED_END)].copy()
    lb_w0["rid"] = lb_w0["repo_norm"].map(rid)
    lb_w0["num"] = lb_w0["instance_id"].map(_num)
    in_kpre = lb_w0[lb_w0["rid"].isin(K_pre_elig)]
    raw_keys = {(rid(r["repo"]), r["number"]) for r in k_w0}
    cand_keys = {(r["m"]["id"], r["number"]) for r in cand_k_w0}
    pairs = {(int(a_), int(b_)) for a_, b_ in zip(in_kpre["rid"], in_kpre["num"])}   # base PRs (dedupes _interface variants)
    hit = len(pairs & cand_keys)
    y_lb = hit / len(cand_k_w0) if cand_k_w0 else 0.0
    calibration = {
        "window_utc": [_iso(w0[0]), _iso(w0[1])],
        "published_post_release_python_tasks": len(lb_w0),
        "published_tasks_in_prior_known_buildable_eligible_repos": len(in_kpre),
        "published_base_prs_in_those_repos": len(pairs),
        "our_stage1_candidates_in_those_repos": len(cand_k_w0),
        "published_base_prs_found_by_our_search": len(pairs & raw_keys),
        "published_base_prs_passing_our_stage1_filters": hit,
        "published_per_stage1_candidate": round(y_lb, 4),
        "published_per_stage1_candidate_ci95_wilson": wilson(hit, len(cand_k_w0)),
        "all_published_in_those_repos_per_stage1_candidate": round(len(pairs) / len(cand_k_w0), 4) if cand_k_w0 else None,
        "funnel": f_k_w0,
        "note": ("The published monthly set is a curated subset (appendix-H filters, including an LLM difficulty "
                 "label), so this rate is a lower bound on what the full pipeline produces."),
    }

    # --- projection ---------------------------------------------------------------------------
    gold = GOLD_PRIOR["kept"] / GOLD_PRIOR["total"]
    paper = PAPER_YIELD["valid"] / PAPER_YIELD["candidates"]
    exp62 = PUBLISHED_TIER_A * gold
    n_k, n_k_cap = len(cand_k_w1), capped(cand_k_w1, PER_REPO_CAP)
    y_cap = (calibration["published_base_prs_passing_our_stage1_filters"] / capped(cand_k_w0, PER_REPO_CAP)
             if cand_k_w0 else 0.0)
    ci = calibration["published_per_stage1_candidate_ci95_wilson"]
    projection = {
        "expected_usable_from_published_62": round(exp62, 1),
        "new_usable_tasks_needed": {str(x): math.ceil(x - exp62) for x in TARGETS},
        "gold_revalidation_keep_rate": round(gold, 4),
        "known_buildable_stage1_candidates": n_k,
        "known_buildable_stage1_candidates_capped": {"cap_per_repo": PER_REPO_CAP, "candidates": n_k_cap},
        "scenarios_known_buildable_only": [
            {"yield": "calibrated on the published window (curated subset; lower bound)", "rate": round(y_lb, 4),
             "expected_usable": round(n_k * y_lb * gold),
             "expected_usable_ci95": [round(n_k * x * gold) for x in ci],
             "expected_usable_capped": round(n_k_cap * y_cap * gold),
             "capped_note": ("uses the rate measured on capped calibration candidates; the cap binds less over the "
                             "41-day calibration window than over the 167-day mining window, so this is rough")},
            {"yield": "SWE-rebench full pipeline (21,336 / 153,400)", "rate": round(paper, 4),
             "expected_usable": round(n_k * paper * gold), "expected_usable_capped": round(n_k_cap * paper * gold)},
        ],
        "cap_sensitivity_candidates": {str(c): capped(cand_k_w1, c) for c in (10, 20, 50)},
        "conversion_rate_needed_under_cap": {
            str(c): {str(x): round(math.ceil(x - exp62) / (capped(cand_k_w1, c) * gold), 4) for x in TARGETS}
            for c in (10, 20, 50)} if n_k else None,
        "calibration_window_capped": {"cap_per_repo": PER_REPO_CAP, "capped_candidates": capped(cand_k_w0, PER_REPO_CAP),
                                      "published_per_capped_candidate": round(y_cap, 4),
                                      "max_published_per_repo": int(in_kpre.groupby("rid").size().max()) if len(in_kpre) else 0},
        "conversion_rate_needed_known_buildable_only": {
            str(x): round(math.ceil(x - exp62) / (n_k * gold), 4) if n_k else None for x in TARGETS},
        "outside_known_buildable_stage1_estimate": sample_out["W1"]["estimated_stage1_candidates_outside_known_buildable"],
        "caveat": "Planning estimates, not measurements. Real counts exist only after environments are built and "
                  "gold patches are validated.",
    }

    tier_b = build_tier_b(lb_py, sbl, v1, train, rid, meta, train_ids, dev_ids, option_b_ids, a.tier_b_csv)

    k_summary = {
        "window_utc": [_iso(w1[0]), _iso(w1[1])],
        "repos_in_universe": len(K_ids), "eligible_repos_searched": len(K_elig) if not a.smoke else 60,
        "funnel": f_k_w1, "stage1_candidates": n_k, "stage1_candidate_repos": len({r["m"]["id"] for r in cand_k_w1}),
        "issue_also_created_after_release": sum(r["issue_post_release"] for r in cand_k_w1),
        "benchmark_subset_shape": sum(r["leaderboard_shape"] for r in cand_k_w1),
        "by_month": dict(sorted(Counter(r["created"][:7] for r in cand_k_w1).items())),
        "max_per_repo": max(Counter(r["m"]["id"] for r in cand_k_w1).values(), default=0),
        "top_repos": [[id_name.get(i, str(i)), n] for i, n in Counter(r["m"]["id"] for r in cand_k_w1).most_common(10)],
        "repos_by_candidate_count": dict(sorted(Counter(
            "1" if n == 1 else "2-9" if n < 10 else "10-49" if n < 50 else "50+"
            for n in Counter(r["m"]["id"] for r in cand_k_w1).values()).items())),
        "candidates_by_star_band": dict(sorted(Counter(
            "<100" if r["m"]["stars"] < 100 else "100-999" if r["m"]["stars"] < 1000 else ">=1000"
            for r in cand_k_w1).items())),
        "licenses": dict(Counter(r["m"]["spdx"] for r in cand_k_w1).most_common()),
    }
    report = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": "analysis/post_release_mining_feasibility.py", "smoke_run": a.smoke,
        "parameters": {
            "release_cutoff_utc": _iso(RELEASE), "published_coverage_end_utc": _iso(PUBLISHED_END),
            "mining_window_utc": [_iso(w1[0]), _iso(w1[1])], "merged_before_utc_day": a.as_of,
            "tier_b_window_utc": [_iso(TIER_B_START), _iso(RELEASE)], "seed": SEED,
            "hours_sampled": {"W1": HOURS_W1, "W0": HOURS_W0}, "bootstrap_reps": BOOTSTRAP_REPS,
            "repo_filters": REPO_STEPS, "pr_filters": PR_STEPS, "min_python_share": MIN_PYTHON_SHARE,
            "min_issue_chars": MIN_ISSUE_CHARS, "files_changed": [FILES_MIN, FILES_MAX],
            "test_path_regex": TEST_PATH.pattern,
            "benchmark_subset_shape": {"max_non_test_files": LB_MAX_NONTEST_FILES, "issue_words": list(LB_ISSUE_WORDS)},
            "development_repos_excluded": DEV_REPOS, "option_b_removed_repos": option_b,
            "open_licenses": "post_release_inventory.OPEN_LICENSES (OSI-approved SPDX ids or public domain)",
            "dataset_revisions": {"nebius/SWE-rebench-leaderboard": lb_rev, "SWE-bench-Live/SWE-bench-Live": sbl_rev,
                                  "nebius/SWE-rebench-V2": train_rev, "nebius/SWE-rebench": v1_rev},
        },
        "training_pool_after_option_b": option_b_check,
        "tier_a": {
            "global_top_of_funnel": {"query": base_global, "monthly_counts": monthly,
                                     "mining_window_count": count_w1, "calibration_window_count": count_w0},
            "global_random_hour_samples": sample_out,
            "known_buildable_universe": k_summary,
            "calibration": calibration,
            "projection": projection,
        },
        "tier_b": tier_b,
        "github_requests": dict(sorted(STATS.items())),
    }
    Path(a.out_json).write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")

    cols = ["found_by", "repo", "pr_number", "pr_url", "pr_created_utc", "merged_utc", "issue_number",
            "issue_created_utc", "issue_post_release", "changed_files", "test_files", "non_test_files",
            "benchmark_subset_shape", "spdx_license", "stars", "python_share", "env_class"]
    seen, out_rows = set(), []
    for found_by, rows in (("known_buildable_complete", cand_k_w1), ("global_hour_sample", sample_cand_w1)):
        for r in sorted(rows, key=lambda r: (r["m"]["name"].lower(), r["number"])):
            if r["node_id"] in seen:
                continue
            seen.add(r["node_id"])
            out_rows.append({"found_by": found_by, "repo": r["m"]["name"], "pr_number": r["number"],
                             "pr_url": f"https://github.com/{r['m']['name']}/pull/{r['number']}",
                             "pr_created_utc": r["created"], "merged_utc": r["merged"],
                             "issue_number": r["issue"]["number"], "issue_created_utc": r["issue"]["created"],
                             "issue_post_release": int(r["issue_post_release"]), "changed_files": r["d"]["changed_files"],
                             "test_files": r["test_files"], "non_test_files": r["non_test_files"],
                             "benchmark_subset_shape": int(r["leaderboard_shape"]), "spdx_license": r["m"]["spdx"],
                             "stars": r["m"]["stars"], "python_share": r["m"]["python_share"], "env_class": r["env_class"]})
    with open(a.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out_rows)
    log(json.dumps({"known_buildable_stage1": n_k, "scenarios": projection["scenarios_known_buildable_only"],
                    "tier_b_final": tier_b["funnel"][-1], "requests": dict(STATS)}, indent=1, default=str))
    return 0


def build_tier_b(lb_py, sbl, v1, train, rid, meta, train_ids, dev_ids, option_b_ids, out_csv):
    """Published tasks created in [2025-02-01, 2026-04-02) with an environment, outside training and development repos."""
    import pandas as pd
    inwin = lambda df: df[(df["created_at_utc"] >= TIER_B_START) & (df["created_at_utc"] < RELEASE)]  # noqa: E731
    v2_removed = train[train["rid"].isin(option_b_ids)]
    parts = []
    for name, df in (("swe_rebench_leaderboard", lb_py), ("swe_rebench_v1", v1[v1["has_env"]]),
                     ("swe_bench_live", sbl), ("swe_rebench_v2_option_b_repos", v2_removed)):
        d = inwin(df).copy()
        d["source"] = name
        parts.append(d[["source", "repo_norm", "instance_id", "created_at_utc"]])
    b = pd.concat(parts, ignore_index=True)
    b["rid"] = b["repo_norm"].map(rid)
    b["num"] = b["instance_id"].map(_num)
    steps = [{"step": "published rows created 2025-02-01 .. 2026-04-01 with an environment", "tasks": len(b),
              "repos": int(b["repo_norm"].nunique()), "by_source": b["source"].value_counts().to_dict()}]
    b = b[b["rid"].notna()].copy()
    b["rid"] = b["rid"].astype(int)
    steps.append({"step": "repository resolves on GitHub", "tasks": len(b), "repos": int(b["rid"].nunique())})
    b["prio"] = b["source"].map({"swe_rebench_leaderboard": 0, "swe_rebench_v1": 1, "swe_bench_live": 2,
                                 "swe_rebench_v2_option_b_repos": 3})
    b = b.sort_values(["prio", "instance_id"]).drop_duplicates(subset=["rid", "num"], keep="first")
    steps.append({"step": "one row per base pull request (across sources and _interface variants)",
                  "tasks": len(b), "repos": int(b["rid"].nunique())})
    b = b[~b["rid"].isin(dev_ids)]
    steps.append({"step": "outside development repositories", "tasks": len(b), "repos": int(b["rid"].nunique())})
    b = b[~b["rid"].isin(train_ids)]
    steps.append({"step": "outside training pool (after Option B)", "tasks": len(b), "repos": int(b["rid"].nunique())})
    rec = lambda n: meta.get(INV.norm_repo(n)) or {}  # noqa: E731
    b["spdx"] = b["repo_norm"].map(lambda n: rec(n).get("spdx"))
    b["canonical"] = b["repo_norm"].map(lambda n: rec(n).get("name"))
    b = b[[license_ok(s, n) for s, n in zip(b["spdx"], b["repo_norm"])]]
    steps.append({"step": "open repository license", "tasks": len(b), "repos": int(b["rid"].nunique()),
                  "by_source": b["source"].value_counts().to_dict()})
    b = b.sort_values(["created_at_utc", "instance_id"])
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "instance_id", "repo", "created_at_utc", "spdx_license"])
        for r in b.itertuples():
            w.writerow([r.source, r.instance_id, r.canonical, r.created_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), r.spdx])
    per = Counter(b["rid"])
    gold = GOLD_PRIOR["kept"] / GOLD_PRIOR["total"]
    return {"window_utc": [_iso(TIER_B_START), _iso(RELEASE)], "funnel": steps,
            "by_month": dict(sorted(Counter(b["created_at_utc"].dt.strftime("%Y-%m")).items())),
            "max_per_repo": max(per.values(), default=0),
            "capped_per_repo": {"cap": PER_REPO_CAP, "tasks": sum(min(v, PER_REPO_CAP) for v in per.values())},
            "expected_usable_after_gold_validation": round(len(b) * gold),
            "note": ("Environment = prebuilt image referenced (SWE-rebench sources) or documented per instance "
                     "(SWE-bench-Live); tags are checked at build time. Tier B is never reported as post-release.")}


if __name__ == "__main__":
    raise SystemExit(main())
